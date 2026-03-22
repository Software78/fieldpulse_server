from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework import status
from uuid import uuid4

from .models import Job, ChecklistSchema

User = get_user_model()


class JobAPITests(APITestCase):
    def setUp(self):
        """Set up test data"""
        # Create test users
        self.technician1 = User.objects.create_user(
            username='tech1',
            email='tech1@example.com',
            password='testpass123'
        )
        self.technician2 = User.objects.create_user(
            username='tech2',
            email='tech2@example.com',
            password='testpass123'
        )
        
        # Create test jobs for technician1
        now = timezone.now()
        self.job1 = Job.objects.create(
            technician=self.technician1,
            customer_name='John Doe',
            customer_phone='555-1234',
            address='123 Main St',
            latitude=40.7128,
            longitude=-74.0060,
            job_description='Fix plumbing',
            notes='Customer prefers morning visits',
            scheduled_start=now + timezone.timedelta(hours=2),
            scheduled_end=now + timezone.timedelta(hours=4),
            status='pending'
        )
        
        self.job2 = Job.objects.create(
            technician=self.technician1,
            customer_name='Jane Smith',
            customer_phone='555-5678',
            address='456 Oak Ave',
            latitude=40.7589,
            longitude=-73.9851,
            job_description='Install new AC',
            notes='',
            scheduled_start=now + timezone.timedelta(hours=6),
            scheduled_end=now + timezone.timedelta(hours=8),
            status='in_progress'
        )
        
        # Create test job for technician2 (should not be visible to technician1)
        self.job3 = Job.objects.create(
            technician=self.technician2,
            customer_name='Bob Wilson',
            customer_phone='555-9999',
            address='789 Pine Rd',
            latitude=40.7489,
            longitude=-73.9680,
            job_description='Repair electrical',
            notes='',
            scheduled_start=now + timezone.timedelta(hours=1),
            scheduled_end=now + timezone.timedelta(hours=3),
            status='completed'
        )
        
        # Create overdue job for technician1
        self.overdue_job = Job.objects.create(
            technician=self.technician1,
            customer_name='Overdue Customer',
            customer_phone='555-0000',
            address='999 Overdue St',
            latitude=40.7000,
            longitude=-74.0000,
            job_description='Overdue task',
            notes='',
            scheduled_start=now - timezone.timedelta(hours=3),
            scheduled_end=now - timezone.timedelta(hours=1),
            status='pending'
        )
        
        # Add checklist schema to job1
        ChecklistSchema.objects.create(
            job=self.job1,
            fields=[
                {'id': 'field1', 'type': 'text', 'label': 'Description', 'required': True},
                {'id': 'field2', 'type': 'checkbox', 'label': 'Completed', 'required': False}
            ],
            version=1
        )
        
        # Authenticate as technician1
        self.client.force_authenticate(user=self.technician1)

    def test_authenticated_user_gets_only_their_jobs(self):
        """Test that authenticated user only gets their own jobs"""
        response = self.client.get('/api/jobs/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should only return jobs for technician1 (job1, job2, overdue_job)
        job_ids = [job['id'] for job in response.data['results']]
        expected_ids = [str(self.job1.id), str(self.job2.id), str(self.overdue_job.id)]
        
        self.assertEqual(len(job_ids), 3)
        self.assertEqual(set(job_ids), set(expected_ids))
        
        # Should not include job3 (belongs to technician2)
        self.assertNotIn(str(self.job3.id), job_ids)

    def test_filter_by_status_works(self):
        """Test filtering by status"""
        # Filter by pending status
        response = self.client.get('/api/jobs/?status=pending')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        expected_ids = [str(self.job1.id), str(self.overdue_job.id)]
        
        self.assertEqual(len(job_ids), 2)
        self.assertEqual(set(job_ids), set(expected_ids))
        
        # Filter by in_progress status
        response = self.client.get('/api/jobs/?status=in_progress')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        expected_ids = [str(self.job2.id)]
        
        self.assertEqual(len(job_ids), 1)
        self.assertEqual(job_ids, expected_ids)

    def test_search_by_customer_name_works(self):
        """Test search functionality"""
        # Search by customer name
        response = self.client.get('/api/jobs/?search=John')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        expected_ids = [str(self.job1.id)]
        
        self.assertEqual(len(job_ids), 1)
        self.assertEqual(job_ids, expected_ids)
        
        # Search by address
        response = self.client.get('/api/jobs/?search=Oak')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        expected_ids = [str(self.job2.id)]
        
        self.assertEqual(len(job_ids), 1)
        self.assertEqual(job_ids, expected_ids)
        
        # Search by job ID
        response = self.client.get(f'/api/jobs/?search={self.job1.id}')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job_ids = [job['id'] for job in response.data['results']]
        expected_ids = [str(self.job1.id)]
        
        self.assertEqual(len(job_ids), 1)
        self.assertEqual(job_ids, expected_ids)

    def test_cursor_pagination_returns_correct_next_cursor(self):
        """Test cursor pagination"""
        response = self.client.get('/api/jobs/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check pagination structure
        self.assertIn('results', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        
        # Should have results
        self.assertTrue(len(response.data['results']) > 0)
        
        # Test next page (if available)
        if response.data['next']:
            next_response = self.client.get(response.data['next'])
            self.assertEqual(next_response.status_code, status.HTTP_200_OK)
            self.assertIn('results', next_response.data)

    def test_job_detail_view_returns_full_details(self):
        """Test job detail view includes checklist schema"""
        response = self.client.get(f'/api/jobs/{self.job1.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check all expected fields are present
        expected_fields = [
            'id', 'customer_name', 'customer_phone', 'address', 'latitude', 'longitude',
            'scheduled_start', 'scheduled_end', 'status', 'is_overdue', 'server_updated_at',
            'job_description', 'notes', 'checklist_schema'
        ]
        
        for field in expected_fields:
            self.assertIn(field, response.data)
        
        # Check checklist schema is included
        self.assertIn('checklist_schema', response.data)
        self.assertIn('fields', response.data['checklist_schema'])
        self.assertEqual(response.data['checklist_schema']['version'], 1)

    def test_job_detail_view_404_for_other_user_job(self):
        """Test that user gets 404 for other user's job"""
        response = self.client.get(f'/api/jobs/{self.job3.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_status_update_validates_transitions(self):
        """Test status update validation"""
        # Test valid transition: pending -> in_progress
        response = self.client.patch(
            f'/api/jobs/{self.job1.id}/status/',
            {'status': 'in_progress'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job1.refresh_from_db()
        self.assertEqual(self.job1.status, 'in_progress')
        
        # Test valid transition: in_progress -> completed
        response = self.client.patch(
            f'/api/jobs/{self.job2.id}/status/',
            {'status': 'completed'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job2.refresh_from_db()
        self.assertEqual(self.job2.status, 'completed')
        
        # Test invalid transition: pending -> completed (should fail)
        response = self.client.patch(
            f'/api/jobs/{self.overdue_job.id}/status/',
            {'status': 'completed'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid status transition', response.data['status'][0])
        
        # Test invalid transition: completed -> pending (should fail)
        response = self.client.patch(
            f'/api/jobs/{self.job2.id}/status/',
            {'status': 'pending'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid status transition', response.data['status'][0])

    def test_status_update_only_accepts_status_field(self):
        """Test that status endpoint only accepts status field"""
        response = self.client.patch(
            f'/api/jobs/{self.job1.id}/status/',
            {'status': 'in_progress', 'customer_name': 'New Name'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Only status field is allowed', response.data['detail'])

    def test_unauthenticated_user_denied_access(self):
        """Test that unauthenticated users cannot access endpoints"""
        self.client.force_authenticate(user=None)
        
        # Test list endpoint
        response = self.client.get('/api/jobs/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test detail endpoint
        response = self.client.get(f'/api/jobs/{self.job1.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Test status endpoint
        response = self.client.patch(f'/api/jobs/{self.job1.id}/status/', {'status': 'in_progress'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_jobs_sorted_by_scheduled_start(self):
        """Test that jobs are sorted by scheduled_start"""
        response = self.client.get('/api/jobs/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        jobs = response.data['results']
        
        # Jobs should be sorted by scheduled_start in ascending order
        scheduled_starts = [job['scheduled_start'] for job in jobs]
        
        # Check that scheduled_starts are in ascending order
        self.assertEqual(scheduled_starts, sorted(scheduled_starts))
