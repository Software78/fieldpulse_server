from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch
import json

from apps.jobs.models import Job, ChecklistResponse
from apps.sync.conflict import detect_conflict, build_conflict_response

User = get_user_model()


class ConflictDetectionTestCase(TestCase):
    """Test conflict detection logic"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.job = Job.objects.create(
            technician=self.user,
            customer_name='Test Customer',
            customer_phone='1234567890',
            address='Test Address',
            job_description='Test Job',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
    def test_detect_conflict_returns_true_when_server_is_newer(self):
        """Test that detect_conflict returns True when server was modified after client"""
        # Create a response with server timestamp
        response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'value1'},
            is_complete=False
        )
        
        # Simulate client having older data
        client_modified_at = response.last_modified_at - timedelta(minutes=5)
        
        # Should detect conflict
        self.assertTrue(detect_conflict(response, client_modified_at))
        
    def test_detect_conflict_returns_false_when_client_is_newer(self):
        """Test that detect_conflict returns False when client has newer data"""
        # Create a response with server timestamp
        response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'value1'},
            is_complete=False
        )
        
        # Simulate client having newer data
        client_modified_at = response.last_modified_at + timedelta(minutes=5)
        
        # Should not detect conflict
        self.assertFalse(detect_conflict(response, client_modified_at))
        
    def test_detect_conflict_returns_false_when_no_response(self):
        """Test that detect_conflict returns False when no response exists"""
        client_modified_at = timezone.now()
        
        # Should not detect conflict when no response
        self.assertFalse(detect_conflict(None, client_modified_at))
        
    def test_detect_conflict_returns_false_when_no_client_timestamp(self):
        """Test that detect_conflict returns False when no client timestamp provided"""
        response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'value1'},
            is_complete=False
        )
        
        # Should not detect conflict when no client timestamp
        self.assertFalse(detect_conflict(response, None))
        
    def test_build_conflict_response(self):
        """Test that build_conflict_response returns proper conflict payload"""
        response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'server_value'},
            is_complete=False
        )
        
        client_data = {
            'data': {'field1': 'client_value'},
            'client_modified_at': timezone.now()
        }
        
        conflict_response = build_conflict_response(client_data, response)
        
        self.assertEqual(conflict_response['client_version']['data'], {'field1': 'client_value'})
        self.assertEqual(conflict_response['client_version']['client_modified_at'], client_data['client_modified_at'])
        self.assertEqual(conflict_response['server_version']['data'], {'field1': 'server_value'})
        self.assertEqual(conflict_response['server_version']['last_modified_at'], response.last_modified_at)


class ChecklistViewTestCase(APITestCase):
    """Test checklist submission endpoint"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        self.job = Job.objects.create(
            technician=self.user,
            customer_name='Test Customer',
            customer_phone='1234567890',
            address='Test Address',
            job_description='Test Job',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=2),
            status='in_progress'
        )
        self.other_job = Job.objects.create(
            technician=self.other_user,
            customer_name='Other Customer',
            customer_phone='0987654321',
            address='Other Address',
            job_description='Other Job',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        self.client.force_authenticate(user=self.user)
        
    def test_get_checklist_returns_existing_response(self):
        """Test GET returns existing checklist response"""
        # Create a checklist response
        response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'value1', 'field2': 'value2'},
            is_complete=False
        )
        
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data'], {'field1': 'value1', 'field2': 'value2'})
        self.assertEqual(response.data['is_complete'], False)
        
    def test_get_checklist_returns_404_when_no_response(self):
        """Test GET returns 404 when no checklist response exists"""
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], 'No checklist response found for this job')
        
    def test_get_checklist_returns_404_for_other_user_job(self):
        """Test GET returns 404 when trying to access another user's job"""
        url = f'/api/jobs/{self.other_job.id}/checklist/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
    def test_post_creates_response_on_first_submit(self):
        """Test POST creates response on first submit"""
        data = {
            'data': {'field1': 'value1', 'field2': 'value2'},
            'client_modified_at': timezone.now(),
            'is_complete': False
        }
        
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data'], {'field1': 'value1', 'field2': 'value2'})
        self.assertEqual(response.data['is_complete'], False)
        
        # Verify it was created in database
        checklist_response = ChecklistResponse.objects.get(job=self.job)
        self.assertEqual(checklist_response.data, {'field1': 'value1', 'field2': 'value2'})
        self.assertEqual(checklist_response.is_complete, False)
        
    def test_post_returns_409_on_conflict(self):
        """Test POST returns 409 on conflict"""
        # Create existing response
        existing_response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'old_value'},
            is_complete=False
        )
        
        # Simulate client having older data
        client_modified_at = existing_response.last_modified_at - timedelta(minutes=5)
        
        data = {
            'data': {'field1': 'new_value'},
            'client_modified_at': client_modified_at,
            'is_complete': False
        }
        
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data['error'], 'conflict')
        self.assertEqual(response.data['message'], 'Job was modified on the server while you were offline.')
        self.assertEqual(response.data['client_version']['data'], {'field1': 'new_value'})
        self.assertEqual(response.data['server_version']['data'], {'field1': 'old_value'})
        
    def test_post_with_force_true_overwrites_despite_conflict(self):
        """Test POST with force=True overwrites despite conflict"""
        # Create existing response
        existing_response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'old_value'},
            is_complete=False
        )
        
        # Simulate client having older data
        client_modified_at = existing_response.last_modified_at - timedelta(minutes=5)
        
        data = {
            'data': {'field1': 'new_value'},
            'client_modified_at': client_modified_at,
            'is_complete': False,
            'force': True
        }
        
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data'], {'field1': 'new_value'})
        
        # Verify it was updated in database
        checklist_response = ChecklistResponse.objects.get(job=self.job)
        self.assertEqual(checklist_response.data, {'field1': 'new_value'})
        
    def test_completing_checklist_sets_job_status_to_completed(self):
        """Test completing checklist sets job status to completed"""
        data = {
            'data': {'field1': 'value1'},
            'client_modified_at': timezone.now(),
            'is_complete': True
        }
        
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['is_complete'], True)
        self.assertIsNotNone(response.data['completed_at'])
        
        # Verify job status was updated
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        
        # Verify checklist response has completed_at
        checklist_response = ChecklistResponse.objects.get(job=self.job)
        self.assertIsNotNone(checklist_response.completed_at)
        
    def test_post_updates_existing_response_without_conflict(self):
        """Test POST updates existing response when no conflict"""
        # Create existing response
        existing_response = ChecklistResponse.objects.create(
            job=self.job,
            data={'field1': 'old_value'},
            is_complete=False
        )
        
        # Simulate client having newer data
        client_modified_at = existing_response.last_modified_at + timedelta(minutes=5)
        
        data = {
            'data': {'field1': 'updated_value'},
            'client_modified_at': client_modified_at,
            'is_complete': True
        }
        
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data'], {'field1': 'updated_value'})
        self.assertEqual(response.data['is_complete'], True)
        
        # Verify job status was updated
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'completed')
        
    def test_post_returns_400_for_invalid_data(self):
        """Test POST returns 400 for invalid data"""
        data = {
            'data': 'not_a_dict',  # Invalid data type
            'client_modified_at': timezone.now(),
            'is_complete': False
        }
        
        url = f'/api/jobs/{self.job.id}/checklist/'
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
    def test_post_returns_404_for_other_user_job(self):
        """Test POST returns 404 when trying to modify another user's job"""
        data = {
            'data': {'field1': 'value1'},
            'client_modified_at': timezone.now(),
            'is_complete': False
        }
        
        url = f'/api/jobs/{self.other_job.id}/checklist/'
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
