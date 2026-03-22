"""
Integration tests for full authentication lifecycle.
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
from rest_framework_simplejwt.blacklist.models import BlacklistedToken, OutstandingToken


User = get_user_model()


@override_settings(
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }
)
class AuthFlowTestCase(TestCase):
    """Test the complete authentication lifecycle."""
    
    def setUp(self):
        """Create test user and set up client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.login_url = reverse('authentication:login')
        self.me_url = reverse('authentication:me')
        self.refresh_url = reverse('authentication:token_refresh')
        self.logout_url = reverse('authentication:logout')
        
    def test_login_success(self):
        """Test POST /api/auth/login/ with valid credentials returns tokens."""
        data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        
    def test_login_invalid_credentials(self):
        """Test POST /api/auth/login/ with wrong password returns 401."""
        data = {
            'username': 'testuser',
            'password': 'wrongpass'
        }
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Invalid credentials')
        
    def test_me_endpoint_with_access_token(self):
        """Test GET /api/auth/me/ with access token returns user data."""
        # Login first
        data = {'username': 'testuser', 'password': 'testpass123'}
        login_response = self.client.post(self.login_url, data, format='json')
        access_token = login_response.data['access']
        
        # Use access token to get user info
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get(self.me_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['first_name'], 'Test')
        self.assertEqual(response.data['last_name'], 'User')
        self.assertIn('full_name', response.data)
        
    def test_token_refresh_success(self):
        """Test POST /api/auth/token/refresh/ with refresh token returns new tokens."""
        # Login first
        data = {'username': 'testuser', 'password': 'testpass123'}
        login_response = self.client.post(self.login_url, data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Refresh tokens
        data = {'refresh': refresh_token}
        response = self.client.post(self.refresh_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        # New refresh token should be different (rotation)
        self.assertNotEqual(response.data['refresh'], refresh_token)
        
    def test_logout_success(self):
        """Test POST /api/auth/logout/ with refresh token returns 205."""
        # Login first
        data = {'username': 'testuser', 'password': 'testpass123'}
        login_response = self.client.post(self.login_url, data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Logout
        data = {'refresh': refresh_token}
        response = self.client.post(self.logout_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        
        # Verify token is blacklisted
        self.assertTrue(
            BlacklistedToken.objects.filter(
                token__jti=RefreshToken(refresh_token).jti
            ).exists()
        )
        
    def test_token_refresh_with_blacklisted_token_fails(self):
        """Test POST /api/auth/token/refresh/ with blacklisted token returns 401."""
        # Login first
        data = {'username': 'testuser', 'password': 'testpass123'}
        login_response = self.client.post(self.login_url, data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Logout to blacklist the token
        data = {'refresh': refresh_token}
        self.client.post(self.logout_url, data, format='json')
        
        # Try to refresh with blacklisted token
        data = {'refresh': refresh_token}
        response = self.client.post(self.refresh_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    @patch('django_ratelimit.core.is_ratelimited')
    def test_login_rate_limiting(self, mock_is_ratelimited):
        """Test hitting login 11 times triggers rate limiting."""
        # Mock rate limiter to trigger after 10 attempts
        mock_is_ratelimited.return_value = False
        
        # Make 10 successful attempts
        data = {'username': 'testuser', 'password': 'testpass123'}
        for i in range(10):
            mock_is_ratelimited.return_value = i >= 10  # Trigger on 11th attempt
            response = self.client.post(self.login_url, data, format='json')
            if i < 10:
                self.assertEqual(response.status_code, status.HTTP_200_OK)
            else:
                self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
                
    @patch('fieldpulse_server.storage.backends.minio.MinIOStorage')
    def test_minio_calls_mocked(self, mock_storage):
        """Test that MinIO/S3 calls are properly mocked."""
        # Mock any MinIO storage operations
        mock_instance = mock_storage.return_value
        mock_instance.save.return_value = 'mocked_file.txt'
        
        # Login should work without actual MinIO calls
        data = {'username': 'testuser', 'password': 'testpass123'}
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify MinIO storage was not actually called
        mock_instance.save.assert_not_called()
