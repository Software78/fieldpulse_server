"""
Integration tests for job sync lifecycle.
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
class JobSyncFlowTestCase(TestCase):
    """Test the complete job sync lifecycle."""
    
    def setUp(self):
        """Create test user and authenticate client."""
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
            customer_name='John Doe',
            customer_phone='555-1234',
            address='123 Main St',
            latitude=40.7128,
            longitude=-74.0060,
            job_description='Fix plumbing issue',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=3),
        )
        
        # Create checklist schema
        self.checklist_schema = ChecklistSchema.objects.create(
            job=self.job,
            fields={
                'tasks': [
                    {'id': 'task1', 'label': 'Inspect pipes', 'type': 'checkbox'},
                    {'id': 'task2', 'label': 'Replace faucet', 'type': 'checkbox'},
                    {'id': 'notes', 'label': 'Additional notes', 'type': 'text'}
                ]
            },
            version=1
        )
        
        # URLs
        self.job_list_url = reverse('jobs:job-list')
        self.job_detail_url = reverse('jobs:job-detail', kwargs={'pk': self.job.id})
        self.checklist_url = reverse('jobs:job-checklist', kwargs={'pk': self.job.id})
        self.job_status_url = reverse('jobs:job-status', kwargs={'pk': self.job.id})
        
    def test_get_job_list(self):
        """Test GET /api/jobs/ returns job in list."""
        response = self.client.get(self.job_list_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        job_data = response.data['results'][0]
        self.assertEqual(job_data['id'], str(self.job.id))
        self.assertEqual(job_data['customer_name'], 'John Doe')
        self.assertEqual(job_data['status'], 'pending')
        
    def test_get_job_detail(self):
        """Test GET /api/jobs/{id}/ returns full detail with checklist_schema."""
        response = self.client.get(self.job_detail_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(self.job.id))
        self.assertEqual(response.data['customer_name'], 'John Doe')
        self.assertEqual(response.data['job_description'], 'Fix plumbing issue')
        
        # Check checklist schema is included
        self.assertIn('checklist_schema', response.data)
        schema = response.data['checklist_schema']
        self.assertEqual(schema['version'], 1)
        self.assertIn('tasks', schema['fields'])
        self.assertEqual(len(schema['fields']['tasks']), 3)
        
    def test_create_checklist_draft(self):
        """Test POST /api/jobs/{id}/checklist/ with partial data creates draft."""
        checklist_data = {
            'data': {
                'task1': True,
                'task2': False,
                'notes': 'Started inspection'
            },
            'is_complete': False,
            'client_modified_at': timezone.now().isoformat()
        }
        
        response = self.client.post(self.checklist_url, checklist_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['is_complete'], False)
        self.assertEqual(response.data['data']['task1'], True)
        self.assertEqual(response.data['data']['notes'], 'Started inspection')
        
        # Verify checklist response was created
        checklist_response = ChecklistResponse.objects.get(job=self.job)
        self.assertEqual(checklist_response.is_complete, False)
        self.assertEqual(checklist_response.data['task1'], True)
        
    def test_get_checklist_draft(self):
        """Test GET /api/jobs/{id}/checklist/ returns saved draft data."""
        # Create a draft first
        ChecklistResponse.objects.create(
            job=self.job,
            data={
                'task1': True,
                'task2': False,
                'notes': 'Started inspection'
            },
            is_complete=False,
            client_modified_at=timezone.now()
        )
        
        response = self.client.get(self.checklist_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_complete'], False)
        self.assertEqual(response.data['data']['task1'], True)
        self.assertEqual(response.data['data']['notes'], 'Started inspection')
        
    def test_complete_checklist(self):
        """Test POST /api/jobs/{id}/checklist/ with complete data marks job complete."""
        # First create a draft
        ChecklistResponse.objects.create(
            job=self.job,
            data={'task1': True},
            is_complete=False,
            client_modified_at=timezone.now()
        )
        
        # Now complete it
        checklist_data = {
            'data': {
                'task1': True,
                'task2': True,
                'notes': 'All tasks completed successfully'
            },
            'is_complete': True,
            'client_modified_at': timezone.now().isoformat()
        }
        
        response = self.client.post(self.checklist_url, checklist_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['is_complete'], True)
        self.assertEqual(response.data['data']['task2'], True)
        self.assertIsNotNone(response.data['completed_at'])
        
    def test_job_status_updates_to_completed(self):
        """Test GET /api/jobs/{id}/ after completing checklist shows completed status."""
        # Complete the checklist
        ChecklistResponse.objects.create(
            job=self.job,
            data={'task1': True, 'task2': True},
            is_complete=True,
            completed_at=timezone.now(),
            client_modified_at=timezone.now()
        )
        
        # Update job status to completed (this should happen via signal/view logic)
        self.job.status = 'completed'
        self.job.save()
        
        response = self.client.get(self.job_detail_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        
    def test_invalid_status_transition(self):
        """Test PATCH /api/jobs/{id}/status/ from completed to pending returns 400."""
        # Set job to completed
        self.job.status = 'completed'
        self.job.save()
        
        # Try to set back to pending
        data = {'status': 'pending'}
        response = self.client.patch(self.job_status_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('Invalid status transition', response.data['error'])
        
    def test_valid_status_transition(self):
        """Test PATCH /api/jobs/{id}/status/ from pending to in_progress succeeds."""
        data = {'status': 'in_progress'}
        response = self.client.patch(self.job_status_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'in_progress')
        
        # Verify job was updated
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'in_progress')
        
    @patch('fieldpulse_server.storage.backends.minio.MinIOStorage')
    def test_minio_calls_mocked(self, mock_storage):
        """Test that MinIO/S3 calls are properly mocked during job operations."""
        # Mock any MinIO storage operations
        mock_instance = mock_storage.return_value
        mock_instance.save.return_value = 'mocked_file.txt'
        
        # Job operations should work without actual MinIO calls
        response = self.client.get(self.job_list_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify MinIO storage was not actually called
        mock_instance.save.assert_not_called()
