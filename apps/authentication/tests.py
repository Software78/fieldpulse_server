"""
Tests for authentication app.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


User = get_user_model()


class AuthenticationTestCase(APITestCase):
    """Test cases for authentication endpoints."""

    def setUp(self):
        """Set up test data."""
        self.user_data = {
            'email': 'testuser@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '+1234567890'
        }
        self.user = User.objects.create_user(
            email=self.user_data['email'],
            password=self.user_data['password'],
            first_name=self.user_data['first_name'],
            last_name=self.user_data['last_name'],
            phone=self.user_data['phone']
        )
        self.login_url = reverse('authentication:login')
        self.refresh_url = reverse('authentication:token_refresh')
        self.logout_url = reverse('authentication:logout')
        self.me_url = reverse('authentication:me')
        self.fcm_token_url = reverse('authentication:fcm_token')

    def test_successful_login(self):
        """Test successful user login."""
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        
        # Check user data
        user_data = response.data['user']
        self.assertEqual(user_data['email'], self.user_data['email'])
        self.assertEqual(user_data['first_name'], self.user_data['first_name'])
        self.assertEqual(user_data['last_name'], self.user_data['last_name'])
        self.assertEqual(user_data['phone'], self.user_data['phone'])

    def test_login_wrong_password(self):
        """Test login with wrong password."""
        data = {
            'email': self.user_data['email'],
            'password': 'wrongpassword'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'invalid_credentials')
        self.assertEqual(response.data['message'], 'Invalid email or password.')

    def test_login_nonexistent_user(self):
        """Test login with non-existent user."""
        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpass123'
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'invalid_credentials')
        self.assertEqual(response.data['message'], 'Invalid email or password.')

    def test_login_missing_fields(self):
        """Test login with missing fields."""
        # Missing password
        data = {'email': self.user_data['email']}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'missing_fields')
        
        # Missing email
        data = {'password': self.user_data['password']}
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'missing_fields')

    def test_login_inactive_user(self):
        """Test login with inactive user."""
        self.user.is_active = False
        self.user.save()
        
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        
        response = self.client.post(self.login_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'account_disabled')
        self.assertEqual(response.data['message'], 'Your account has been disabled.')

    def test_token_refresh(self):
        """Test token refresh endpoint."""
        # First login to get tokens
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Refresh the token
        refresh_data = {'refresh': refresh_token}
        response = self.client.post(self.refresh_url, refresh_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertNotEqual(response.data['access'], login_response.data['access'])

    def test_token_refresh_invalid_token(self):
        """Test token refresh with invalid token."""
        data = {'refresh': 'invalid_refresh_token'}
        response = self.client.post(self.refresh_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_success(self):
        """Test successful logout with token blacklisting."""
        # First login to get tokens
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, data, format='json')
        refresh_token = login_response.data['refresh']
        
        # Logout
        logout_data = {'refresh': refresh_token}
        response = self.client.post(self.logout_url, logout_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Successfully logged out.')
        
        # Verify token is blacklisted
        try:
            token = RefreshToken(refresh_token)
            # This should raise an exception if token is blacklisted
            token.check_blacklist()
            self.fail("Token should be blacklisted")
        except Exception:
            # Token is properly blacklisted
            pass

    def test_logout_missing_refresh_token(self):
        """Test logout without refresh token."""
        response = self.client.post(self.logout_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'missing_refresh_token')
        self.assertEqual(response.data['message'], 'Refresh token is required.')

    def test_logout_invalid_refresh_token(self):
        """Test logout with invalid refresh token."""
        data = {'refresh': 'invalid_refresh_token'}
        response = self.client.post(self.logout_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'logout_failed')

    def test_me_endpoint(self):
        """Test getting current user profile."""
        # First login to get token
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, data, format='json')
        access_token = login_response.data['access']
        
        # Use token to access me endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get(self.me_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user_data['email'])
        self.assertEqual(response.data['first_name'], self.user_data['first_name'])
        self.assertEqual(response.data['last_name'], self.user_data['last_name'])
        self.assertEqual(response.data['phone'], self.user_data['phone'])

    def test_me_endpoint_unauthorized(self):
        """Test me endpoint without authentication."""
        response = self.client.get(self.me_url, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fcm_token_update(self):
        """Test updating FCM token."""
        # First login to get token
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, data, format='json')
        access_token = login_response.data['access']
        
        # Update FCM token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        fcm_data = {'fcm_token': 'new_fcm_token_12345'}
        response = self.client.patch(self.fcm_token_url, fcm_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'FCM token updated successfully.')
        self.assertEqual(response.data['fcm_token'], 'new_fcm_token_12345')
        
        # Verify token was updated in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.fcm_token, 'new_fcm_token_12345')

    def test_fcm_token_clear(self):
        """Test clearing FCM token."""
        # First login to get token
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, data, format='json')
        access_token = login_response.data['access']
        
        # Clear FCM token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        fcm_data = {'fcm_token': ''}
        response = self.client.patch(self.fcm_token_url, fcm_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['fcm_token'], '')
        
        # Verify token was cleared in database
        self.user.refresh_from_db()
        self.assertEqual(self.user.fcm_token, '')

    def test_fcm_token_unauthorized(self):
        """Test updating FCM token without authentication."""
        fcm_data = {'fcm_token': 'new_fcm_token_12345'}
        response = self.client.patch(self.fcm_token_url, fcm_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_fcm_token_invalid_token(self):
        """Test updating FCM token with invalid token."""
        # First login to get token
        data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, data, format='json')
        access_token = login_response.data['access']
        
        # Try to update with invalid token (too long)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        fcm_data = {'fcm_token': 'x' * 256}  # 256 characters, exceeds max_length 255
        response = self.client.patch(self.fcm_token_url, fcm_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'validation_error')


class UserModelTest(TestCase):
    """Test cases for User model."""

    def test_create_user(self):
        """Test creating a regular user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.assertEqual(user.email, 'admin@example.com')
        self.assertTrue(user.check_password('adminpass123'))
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_user_str_method(self):
        """Test User model __str__ method."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.assertEqual(str(user), 'test@example.com')

    def test_user_full_name_property(self):
        """Test User model full_name property."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        
        self.assertEqual(user.full_name, 'John Doe')
        
        # Test with only first name
        user.last_name = ''
        user.save()
        self.assertEqual(user.full_name, 'John')
        
        # Test with only last name
        user.first_name = ''
        user.last_name = 'Doe'
        user.save()
        self.assertEqual(user.full_name, 'Doe')
        
        # Test with no names
        user.first_name = ''
        user.last_name = ''
        user.save()
        self.assertEqual(user.full_name, '')
