"""
Integration tests for media uploads with mocked S3.
"""
import uuid
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.users.models import User
from apps.jobs.models import Job


class MediaUploadTests(TestCase):
    """
    Test cases for photo and signature uploads.
    """
    
    def setUp(self):
        """
        Set up test data.
        """
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test job
        self.job = Job.objects.create(
            technician=self.user,
            customer_name='Test Customer',
            customer_phone='1234567890',
            address='123 Test St',
            job_description='Test job description',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timezone.timedelta(hours=2)
        )
        
        # Create other user's job (for testing ownership)
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        self.other_job = Job.objects.create(
            technician=self.other_user,
            customer_name='Other Customer',
            customer_phone='0987654321',
            address='456 Other St',
            job_description='Other job description',
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timezone.timedelta(hours=2)
        )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
    
    def create_test_image(self, content_type='image/jpeg', filename='test.jpg'):
        """
        Create a test image file.
        """
        return SimpleUploadedFile(
            filename,
            b'fake_image_data',  # Minimal fake image data
            content_type=content_type
        )
    
    def create_test_png(self):
        """
        Create a test PNG file.
        """
        return SimpleUploadedFile(
            'test.png',
            b'fake_png_data',  # Minimal fake PNG data
            content_type='image/png'
        )
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_photo_upload_success(self, mock_upload):
        """
        Test successful photo upload.
        """
        # Mock the S3 upload
        mock_url = 'https://minio.example.com/test-bucket/photos/job_id/field_id/uuid.jpg'
        mock_upload.return_value = mock_url
        
        # Prepare test data
        image_file = self.create_test_image()
        data = {
            'job_id': str(self.job.id),
            'field_id': 'test_field_1',
            'file': image_file,
            'captured_at': timezone.now().isoformat(),
            'latitude': '40.7128',
            'longitude': '-74.0060'
        }
        
        # Make request
        response = self.client.post('/api/media/photos/', data, format='multipart')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('url', response.data)
        self.assertEqual(response.data['url'], mock_url)
        
        # Verify upload was called with correct parameters
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        self.assertEqual(call_args[1]['content_type'], 'image/jpeg')
        self.assertIn('photos/', call_args[0][1])  # S3 key contains 'photos/'
        
        # Verify database record was created
        from apps.media_app.models import PhotoUpload
        photo = PhotoUpload.objects.get(id=response.data['id'])
        self.assertEqual(photo.job, self.job)
        self.assertEqual(photo.field_id, 'test_field_1')
        self.assertEqual(photo.s3_url, mock_url)
        self.assertEqual(photo.latitude, Decimal('40.7128'))
        self.assertEqual(photo.longitude, Decimal('-74.0060'))
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_photo_upload_rejects_non_image_file(self, mock_upload):
        """
        Test that photo upload rejects non-image files.
        """
        # Create non-image file
        text_file = SimpleUploadedFile(
            'test.txt',
            b'this is not an image',
            content_type='text/plain'
        )
        
        data = {
            'job_id': str(self.job.id),
            'field_id': 'test_field_1',
            'file': text_file,
            'captured_at': timezone.now().isoformat()
        }
        
        # Make request
        response = self.client.post('/api/media/photos/', data, format='multipart')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)
        
        # Verify upload was not called
        mock_upload.assert_not_called()
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_photo_upload_rejects_job_not_belonging_to_user(self, mock_upload):
        """
        Test that photo upload rejects jobs not belonging to the user.
        """
        image_file = self.create_test_image()
        data = {
            'job_id': str(self.other_job.id),  # Other user's job
            'field_id': 'test_field_1',
            'file': image_file,
            'captured_at': timezone.now().isoformat()
        }
        
        # Make request
        response = self.client.post('/api/media/photos/', data, format='multipart')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('job_id', response.data)
        
        # Verify upload was not called
        mock_upload.assert_not_called()
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_photo_upload_validates_coordinates(self, mock_upload):
        """
        Test that photo upload validates GPS coordinates.
        """
        image_file = self.create_test_image()
        
        # Test invalid latitude
        data = {
            'job_id': str(self.job.id),
            'field_id': 'test_field_1',
            'file': image_file,
            'captured_at': timezone.now().isoformat(),
            'latitude': '91.0',  # Invalid latitude (> 90)
            'longitude': '0.0'
        }
        
        response = self.client.post('/api/media/photos/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_upload.assert_not_called()
        
        # Test missing longitude when latitude provided
        data = {
            'job_id': str(self.job.id),
            'field_id': 'test_field_1',
            'file': self.create_test_image(),  # Need fresh file
            'captured_at': timezone.now().isoformat(),
            'latitude': '40.0'
            # longitude missing
        }
        
        response = self.client.post('/api/media/photos/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_signature_upload_success(self, mock_upload):
        """
        Test successful signature upload.
        """
        # Mock the S3 upload
        mock_url = 'https://minio.example.com/test-bucket/signatures/job_id/field_id/uuid.png'
        mock_upload.return_value = mock_url
        
        # Prepare test data
        png_file = self.create_test_png()
        data = {
            'job_id': str(self.job.id),
            'field_id': 'signature_field_1',
            'file': png_file,
            'captured_at': timezone.now().isoformat()
        }
        
        # Make request
        response = self.client.post('/api/media/signatures/', data, format='multipart')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('url', response.data)
        self.assertEqual(response.data['url'], mock_url)
        
        # Verify upload was called with correct parameters
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        self.assertEqual(call_args[1]['content_type'], 'image/png')
        self.assertIn('signatures/', call_args[0][1])  # S3 key contains 'signatures/'
        
        # Verify database record was created
        from apps.media_app.models import SignatureUpload
        signature = SignatureUpload.objects.get(id=response.data['id'])
        self.assertEqual(signature.job, self.job)
        self.assertEqual(signature.field_id, 'signature_field_1')
        self.assertEqual(signature.s3_url, mock_url)
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_signature_upload_rejects_non_png_file(self, mock_upload):
        """
        Test that signature upload rejects non-PNG files.
        """
        # Create JPEG file instead of PNG
        jpeg_file = self.create_test_image('image/jpeg', 'test.jpg')
        
        data = {
            'job_id': str(self.job.id),
            'field_id': 'signature_field_1',
            'file': jpeg_file,
            'captured_at': timezone.now().isoformat()
        }
        
        # Make request
        response = self.client.post('/api/media/signatures/', data, format='multipart')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)
        
        # Verify upload was not called
        mock_upload.assert_not_called()
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_signature_upload_rejects_job_not_belonging_to_user(self, mock_upload):
        """
        Test that signature upload rejects jobs not belonging to the user.
        """
        png_file = self.create_test_png()
        data = {
            'job_id': str(self.other_job.id),  # Other user's job
            'field_id': 'signature_field_1',
            'file': png_file,
            'captured_at': timezone.now().isoformat()
        }
        
        # Make request
        response = self.client.post('/api/media/signatures/', data, format='multipart')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('job_id', response.data)
        
        # Verify upload was not called
        mock_upload.assert_not_called()
    
    def test_upload_requires_authentication(self):
        """
        Test that upload endpoints require authentication.
        """
        # Logout
        self.client.force_authenticate(user=None)
        
        image_file = self.create_test_image()
        data = {
            'job_id': str(self.job.id),
            'field_id': 'test_field_1',
            'file': image_file,
            'captured_at': timezone.now().isoformat()
        }
        
        # Test photo upload
        response = self.client.post('/api/media/photos/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        # Test signature upload
        png_file = self.create_test_png()
        data = {
            'job_id': str(self.job.id),
            'field_id': 'signature_field_1',
            'file': png_file,
            'captured_at': timezone.now().isoformat()
        }
        
        response = self.client.post('/api/media/signatures/', data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    @patch('apps.media_app.storage.storage.upload_file')
    def test_upload_handles_storage_error(self, mock_upload):
        """
        Test that upload handles storage errors gracefully.
        """
        # Mock storage error
        from botocore.exceptions import ClientError
        mock_upload.side_effect = ClientError(
            error_response={'Error': {'Code': 'StorageError', 'Message': 'Storage failed'}},
            operation_name='PutObject'
        )
        
        image_file = self.create_test_image()
        data = {
            'job_id': str(self.job.id),
            'field_id': 'test_field_1',
            'file': image_file,
            'captured_at': timezone.now().isoformat()
        }
        
        # Make request
        response = self.client.post('/api/media/photos/', data, format='multipart')
        
        # Assertions
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        
        # Verify no database record was created
        from apps.media_app.models import PhotoUpload
        self.assertFalse(PhotoUpload.objects.exists())
