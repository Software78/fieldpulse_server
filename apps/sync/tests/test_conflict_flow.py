"""
Integration tests for conflict detection and resolution.
"""
from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.jobs.models import Job, ChecklistSchema, ChecklistResponse


User = get_user_model()


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
)
class ConflictFlowTestCase(TestCase):
    """Test conflict detection and resolution scenarios."""
    
    def setUp(self):
        """Create test user, job, and authenticate client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testtech',
            email='tech@example.com',
            password='techpass123',
            first_name='Test',
            last_name='Technician'
        )
        
        # Authenticate client
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Create test job with checklist schema
        self.job = Job.objects.create(
            technician=self.user,
            customer_name='Jane Smith',
            customer_phone='555-5678',
            address='456 Oak Ave',
            latitude=40.7589,
            longitude=-73.9851,
            job_description='Repair electrical system',
            scheduled_start=timezone.now() + timedelta(hours=2),
            scheduled_end=timezone.now() + timedelta(hours=4),
        )
        
        # Create checklist schema
        self.checklist_schema = ChecklistSchema.objects.create(
            job=self.job,
            fields={
                'tasks': [
                    {'id': 'task1', 'label': 'Check wiring', 'type': 'checkbox'},
                    {'id': 'task2', 'label': 'Test circuits', 'type': 'checkbox'},
                    {'id': 'notes', 'label': 'Work notes', 'type': 'text'}
                ]
            },
            version=1
        )
        
        # URLs
        self.checklist_url = reverse('jobs:job-checklist', kwargs={'pk': self.job.id})
        self.batch_sync_url = reverse('sync:batch_sync')
        
        # Timestamps for testing
        self.early_timestamp = timezone.now() - timedelta(hours=2)
        self.late_timestamp = timezone.now() - timedelta(minutes=10)
        
    def test_conflict_detection_with_old_client_timestamp(self):
        """Test POST /api/jobs/{id}/checklist/ with old client_modified_at returns 409."""
        # Create existing checklist response on server
        existing_response = ChecklistResponse.objects.create(
            job=self.job,
            data={
                'task1': True,
                'task2': False,
                'notes': 'Initial inspection done'
            },
            is_complete=False,
            client_modified_at=self.late_timestamp,  # Client synced 10 mins ago
            last_modified_at=timezone.now()  # Server modified just now
        )
        
        # Simulate client that synced BEFORE server's last modification
        client_data = {
            'data': {
                'task1': True,
                'task2': True,
                'notes': 'Completed all tasks'
            },
            'is_complete': True,
            'client_modified_at': self.early_timestamp.isoformat()  # 2 hours ago
        }
        
        response = self.client.post(self.checklist_url, client_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('conflict', response.data)
        self.assertIn('client_version', response.data['conflict'])
        self.assertIn('server_version', response.data['conflict'])
        
        # Verify conflict response structure
        conflict = response.data['conflict']
        self.assertEqual(conflict['client_version']['data']['task2'], True)
        self.assertEqual(conflict['server_version']['data']['task2'], False)
        self.assertEqual(
            conflict['server_version']['last_modified_at'],
            existing_response.last_modified_at.isoformat().replace('+00:00', 'Z')
        )
        
    def test_force_overwrite_conflict(self):
        """Test POST /api/jobs/{id}/checklist/ with force=True overwrites data."""
        # Create existing checklist response on server
        ChecklistResponse.objects.create(
            job=self.job,
            data={
                'task1': True,
                'task2': False,
                'notes': 'Server version'
            },
            is_complete=False,
            client_modified_at=self.late_timestamp,
            last_modified_at=timezone.now()
        )
        
        # Force overwrite with client data
        client_data = {
            'data': {
                'task1': True,
                'task2': True,
                'notes': 'Client forced version'
            },
            'is_complete': True,
            'client_modified_at': self.early_timestamp.isoformat(),
            'force': True
        }
        
        response = self.client.post(self.checklist_url, client_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_complete'], True)
        self.assertEqual(response.data['data']['notes'], 'Client forced version')
        
        # Verify data was actually overwritten
        checklist_response = ChecklistResponse.objects.get(job=self.job)
        self.assertEqual(checklist_response.data['notes'], 'Client forced version')
        self.assertEqual(checklist_response.is_complete, True)
        
    def test_batch_sync_mixed_results(self):
        """Test POST /api/sync/batch/ with clean and conflicting jobs returns mixed results."""
        # Create second job for batch testing
        job2 = Job.objects.create(
            technician=self.user,
            customer_name='Bob Johnson',
            customer_phone='555-9999',
            address='789 Pine St',
            job_description='Install new equipment',
            scheduled_start=timezone.now() + timedelta(hours=3),
            scheduled_end=timezone.now() + timedelta(hours=5),
        )
        
        ChecklistSchema.objects.create(
            job=job2,
            fields={
                'tasks': [
                    {'id': 'task1', 'label': 'Install equipment', 'type': 'checkbox'},
                ]
            },
            version=1
        )
        
        # Create existing response for job2 (clean - no conflict)
        ChecklistResponse.objects.create(
            job=job2,
            data={'task1': False},
            is_complete=False,
            client_modified_at=self.early_timestamp,
            last_modified_at=self.early_timestamp
        )
        
        # Create existing response for self.job (conflict scenario)
        ChecklistResponse.objects.create(
            job=self.job,
            data={'task1': False, 'task2': False},
            is_complete=False,
            client_modified_at=self.late_timestamp,
            last_modified_at=timezone.now()
        )
        
        # Batch sync data
        batch_data = {
            'jobs': [
                {
                    'id': str(job2.id),
                    'checklist_data': {
                        'data': {'task1': True},
                        'is_complete': True,
                        'client_modified_at': self.early_timestamp.isoformat()
                    }
                },
                {
                    'id': str(self.job.id),
                    'checklist_data': {
                        'data': {'task1': True, 'task2': True},
                        'is_complete': True,
                        'client_modified_at': self.early_timestamp.isoformat()
                    }
                }
            ]
        }
        
        response = self.client.post(self.batch_sync_url, batch_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        
        results = response.data['results']
        self.assertEqual(len(results), 2)
        
        # Find results for each job
        job2_result = next(r for r in results if r['id'] == str(job2.id))
        job1_result = next(r for r in results if r['id'] == str(self.job.id))
        
        # Job2 should succeed (clean sync)
        self.assertEqual(job2_result['status'], 'success')
        self.assertIn('checklist_data', job2_result)
        
        # Job1 should have conflict
        self.assertEqual(job1_result['status'], 'conflict')
        self.assertIn('conflict', job1_result)
        self.assertIn('client_version', job1_result['conflict'])
        self.assertIn('server_version', job1_result['conflict'])
        
    def test_no_conflict_with_recent_timestamp(self):
        """Test POST with recent client_modified_at succeeds without conflict."""
        # Create existing checklist response
        ChecklistResponse.objects.create(
            job=self.job,
            data={'task1': True},
            is_complete=False,
            client_modified_at=self.early_timestamp,
            last_modified_at=self.early_timestamp
        )
        
        # Client with recent timestamp should succeed
        client_data = {
            'data': {
                'task1': True,
                'task2': True,
                'notes': 'Updated with recent timestamp'
            },
            'is_complete': False,
            'client_modified_at': timezone.now().isoformat()
        }
        
        response = self.client.post(self.checklist_url, client_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['notes'], 'Updated with recent timestamp')
        
    def test_conflict_resolution_with_force_in_batch(self):
        """Test batch sync with force=True resolves conflicts."""
        # Create existing checklist response
        ChecklistResponse.objects.create(
            job=self.job,
            data={'task1': False},
            is_complete=False,
            client_modified_at=self.late_timestamp,
            last_modified_at=timezone.now()
        )
        
        # Batch sync with force
        batch_data = {
            'jobs': [
                {
                    'id': str(self.job.id),
                    'checklist_data': {
                        'data': {'task1': True, 'task2': True},
                        'is_complete': True,
                        'client_modified_at': self.early_timestamp.isoformat(),
                        'force': True
                    }
                }
            ]
        }
        
        response = self.client.post(self.batch_sync_url, batch_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['status'], 'success')
        
        # Verify data was overwritten
        checklist_response = ChecklistResponse.objects.get(job=self.job)
        self.assertEqual(checklist_response.data['task1'], True)
        self.assertEqual(checklist_response.is_complete, True)
        
    @patch('fieldpulse_server.storage.backends.minio.MinIOStorage')
    def test_minio_calls_mocked(self, mock_storage):
        """Test that MinIO/S3 calls are properly mocked during sync operations."""
        # Mock any MinIO storage operations
        mock_instance = mock_storage.return_value
        mock_instance.save.return_value = 'mocked_file.txt'
        
        # Sync operations should work without actual MinIO calls
        client_data = {
            'data': {'task1': True},
            'is_complete': False,
            'client_modified_at': timezone.now().isoformat()
        }
        
        response = self.client.post(self.checklist_url, client_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Verify MinIO storage was not actually called
        mock_instance.save.assert_not_called()
