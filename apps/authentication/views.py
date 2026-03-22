"""
Views for authentication app.
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView

from .serializers import (
    LoginSerializer,
    TokenResponseSerializer,
    UserSerializer,
    FCMTokenSerializer
)
from .models import User


def error_response(error_code, message, details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Standard error response format.
    """
    return Response({
        'error': error_code,
        'message': message,
        'details': details or {}
    }, status=status_code)


@method_decorator(ratelimit(key='ip', rate='10/m', method='POST'), name='post')
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    """
    Login view for user authentication.
    POST /api/auth/login/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        Authenticate user and return tokens.
        """
        serializer = LoginSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            error_data = serializer.errors
            # Extract the first error for consistent format
            if isinstance(error_data, dict) and error_data:
                first_key = list(error_data.keys())[0]
                first_error = error_data[first_key]
                if isinstance(first_error, list) and first_error:
                    if isinstance(first_error[0], dict):
                        return error_response(
                            error_code=first_error[0].get('error', 'validation_error'),
                            message=first_error[0].get('message', 'Validation failed'),
                            details=first_error[0].get('details', {}),
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
                    else:
                        return error_response(
                            error_code='validation_error',
                            message=str(first_error[0]),
                            details={first_key: first_error[0]},
                            status_code=status.HTTP_400_BAD_REQUEST
                        )
        
        user = serializer.validated_data['user']
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        response_data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        }
        
        response_serializer = TokenResponseSerializer(response_data)
        
        return Response(response_serializer.data, status=status.HTTP_200_OK)


@method_decorator(ratelimit(key='user', rate='30/m', method='POST'), name='post')
class TokenRefreshViewCustom(TokenRefreshView):
    """
    Custom token refresh view with rate limiting.
    POST /api/auth/refresh/
    """
    
    def post(self, request, *args, **kwargs):
        """
        Refresh access token with rate limiting.
        """
        try:
            response = super().post(request, *args, **kwargs)
            return response
        except Exception as e:
            return error_response(
                error_code='token_refresh_failed',
                message='Failed to refresh token.',
                details={'error': str(e)},
                status_code=status.HTTP_400_BAD_REQUEST
            )


@method_decorator(ratelimit(key='ip', rate='20/m', method='POST'), name='post')
@method_decorator(csrf_exempt, name='dispatch')
class LogoutView(APIView):
    """
    Logout view to blacklist refresh token.
    POST /api/auth/logout/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Blacklist the submitted refresh token.
        """
        try:
            refresh_token = request.data.get('refresh')
            
            if not refresh_token:
                return error_response(
                    error_code='missing_refresh_token',
                    message='Refresh token is required.',
                    details={},
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response({
                'message': 'Successfully logged out.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return error_response(
                error_code='logout_failed',
                message='Failed to logout.',
                details={'error': str(e)},
                status_code=status.HTTP_400_BAD_REQUEST
            )


class MeView(APIView):
    """
    Get current user profile.
    GET /api/auth/me/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Return current user profile.
        """
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class FCMTokenView(APIView):
    """
    Update FCM token for push notifications.
    PATCH /api/auth/fcm-token/
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        """
        Update user's FCM token.
        """
        serializer = FCMTokenSerializer(data=request.data, partial=True)
        
        if not serializer.is_valid():
            return error_response(
                error_code='validation_error',
                message='Invalid FCM token.',
                details=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        fcm_token = serializer.validated_data.get('fcm_token')
        
        # Update user's FCM token
        request.user.fcm_token = fcm_token
        request.user.save(update_fields=['fcm_token'])
        
        return Response({
            'message': 'FCM token updated successfully.',
            'fcm_token': fcm_token
        }, status=status.HTTP_200_OK)
