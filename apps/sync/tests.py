from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from uuid import uuid4
import json

from apps.jobs.models import Job, ChecklistResponse

User = get_user_model()


class BatchSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        
        self.other_user = User.objects.create_user(
            username='otheruser',
            password='otherpass123',
            email='other@example.com'
        )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # Create test jobs
        self.job1 = Job.objects.create(
            technician=self.user,
            customer_name='Customer 1',
            customer_phone='1234567890',
            address='Address 1',
            job_description='Job 1',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        self.job2 = Job.objects.create(
            technician=self.user,
            customer_name='Customer 2',
            customer_phone='1234567891',
            address='Address 2',
            job_description='Job 2',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        self.job3 = Job.objects.create(
            technician=self.user,
            customer_name='Customer 3',
            customer_phone='1234567892',
            address='Address 3',
            job_description='Job 3',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        # Create a job for another user
        self.other_user_job = Job.objects.create(
            technician=self.other_user,
            customer_name='Other Customer',
            customer_phone='1234567893',
            address='Other Address',
            job_description='Other Job',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        # Create existing checklist response for conflict testing
        self.existing_checklist = ChecklistResponse.objects.create(
            job=self.job2,
            data={'field1': 'old_value', 'field2': 'old_value2'},
            is_complete=False,
            last_modified_at=timezone.now() - timedelta(minutes=5)
        )

    def test_batch_sync_all_success(self):
        """Test batch of 3 jobs, all succeed"""
        client_time = timezone.now()
        payload = {
            'jobs': [
                {
                    'id': str(self.job1.id),
                    'status': 'in_progress',
                    'checklist': {
                        'data': {'field1': 'value1', 'field2': 'value2'},
                        'client_modified_at': client_time.isoformat(),
                        'is_complete': False,
                        'force': False
                    }
                },
                {
                    'id': str(self.job2.id),
                    'status': 'completed',
                    'checklist': {
                        'data': {'field1': 'new_value', 'field2': 'new_value2'},
                        'client_modified_at': client_time.isoformat(),
                        'is_complete': True,
                        'force': True
                    }
                },
                {
                    'id': str(self.job3.id),
                    'status': 'completed'
                }
            ]
        }
        
        response = self.client.post('/api/sync/batch/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
        
        for result in response.data['results']:
            self.assertEqual(result['status'], 'success')
        
        # Verify database changes
        self.job1.refresh_from_db()
        self.job2.refresh_from_db()
        self.job3.refresh_from_db()
        
        self.assertEqual(self.job1.status, 'in_progress')
        self.assertEqual(self.job2.status, 'completed')
        self.assertEqual(self.job3.status, 'completed')
        
        # Verify checklist updates
        checklist1 = ChecklistResponse.objects.get(job=self.job1)
        self.assertEqual(checklist1.data['field1'], 'value1')
        self.assertFalse(checklist1.is_complete)
        
        checklist2 = ChecklistResponse.objects.get(job=self.job2)
        self.assertEqual(checklist2.data['field1'], 'new_value')
        self.assertTrue(checklist2.is_complete)
        self.assertIsNotNone(checklist2.completed_at)

    def test_batch_sync_with_conflict(self):
        """Test batch with one conflict returns mixed results"""
        # Update the existing checklist to make it newer than client time
        self.existing_checklist.last_modified_at = timezone.now()
        self.existing_checklist.save()
        
        client_time = timezone.now() - timedelta(minutes=10)  # Older than server
        payload = {
            'jobs': [
                {
                    'id': str(self.job1.id),
                    'status': 'in_progress',
                    'checklist': {
                        'data': {'field1': 'value1'},
                        'client_modified_at': client_time.isoformat(),
                        'is_complete': False,
                        'force': False
                    }
                },
                {
                    'id': str(self.job2.id),  # This will have conflict
                    'checklist': {
                        'data': {'field1': 'conflict_value'},
                        'client_modified_at': client_time.isoformat(),
                        'is_complete': True,
                        'force': False
                    }
                },
                {
                    'id': str(self.job3.id),
                    'status': 'completed'
                }
            ]
        }
        
        response = self.client.post('/api/sync/batch/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
        
        # Check individual results
        results = {result['id']: result for result in response.data['results']}
        
        self.assertEqual(results[str(self.job1.id)]['status'], 'success')
        self.assertEqual(results[str(self.job2.id)]['status'], 'conflict')
        self.assertEqual(results[str(self.job3.id)]['status'], 'success')
        
        # Verify conflict response structure
        conflict_result = results[str(self.job2.id)]
        self.assertIn('client_version', conflict_result)
        self.assertIn('server_version', conflict_result)
        self.assertEqual(conflict_result['client_version']['data']['field1'], 'conflict_value')
        self.assertEqual(conflict_result['server_version']['data']['field1'], 'old_value')

    def test_batch_sync_rejects_other_user_jobs(self):
        """Test batch rejects jobs not belonging to user"""
        payload = {
            'jobs': [
                {
                    'id': str(self.job1.id),
                    'status': 'in_progress'
                },
                {
                    'id': str(self.other_user_job.id),  # Not belonging to user
                    'status': 'completed'
                },
                {
                    'id': str(self.job2.id),
                    'status': 'completed'
                }
            ]
        }
        
        response = self.client.post('/api/sync/batch/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)
        
        results = {result['id']: result for result in response.data['results']}
        
        self.assertEqual(results[str(self.job1.id)]['status'], 'success')
        self.assertEqual(results[str(self.other_user_job.id)]['status'], 'error')
        self.assertEqual(results[str(self.other_user_job.id)]['message'], 'Job not found')
        self.assertEqual(results[str(self.job2.id)]['status'], 'success')

    def test_batch_sync_force_overwrites_conflict(self):
        """Test batch with force=True on conflict overwrites"""
        # Make server version newer
        self.existing_checklist.last_modified_at = timezone.now()
        self.existing_checklist.save()
        
        client_time = timezone.now() - timedelta(minutes=10)  # Older than server
        payload = {
            'jobs': [
                {
                    'id': str(self.job2.id),
                    'checklist': {
                        'data': {'field1': 'forced_value', 'field2': 'forced_value2'},
                        'client_modified_at': client_time.isoformat(),
                        'is_complete': True,
                        'force': True  # This should overwrite the conflict
                    }
                }
            ]
        }
        
        response = self.client.post('/api/sync/batch/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        result = response.data['results'][0]
        self.assertEqual(result['status'], 'success')
        
        # Verify the data was overwritten
        checklist = ChecklistResponse.objects.get(job=self.job2)
        self.assertEqual(checklist.data['field1'], 'forced_value')
        self.assertEqual(checklist.data['field2'], 'forced_value2')
        self.assertTrue(checklist.is_complete)
        self.assertIsNotNone(checklist.completed_at)

    def test_batch_sync_max_jobs_limit(self):
        """Test that batch sync rejects more than 50 jobs"""
        jobs = []
        for i in range(51):  # Exceeds limit of 50
            jobs.append({
                'id': str(self.job1.id),
                'status': 'in_progress'
            })
        
        payload = {'jobs': jobs}
        
        response = self.client.post('/api/sync/batch/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_sync_invalid_uuid(self):
        """Test batch sync with invalid UUID"""
        payload = {
            'jobs': [
                {
                    'id': 'invalid-uuid',
                    'status': 'in_progress'
                }
            ]
        }
        
        response = self.client.post('/api/sync/batch/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_sync_unauthorized(self):
        """Test batch sync without authentication"""
        self.client.force_authenticate(user=None)
        
        payload = {
            'jobs': [
                {
                    'id': str(self.job1.id),
                    'status': 'in_progress'
                }
            ]
        }
        
        response = self.client.post('/api/sync/batch/', payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
