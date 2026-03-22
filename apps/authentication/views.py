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
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={200: TokenResponseSerializer},
        operation_description="Authenticate user and return JWT tokens"
    )
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
    
    @swagger_auto_schema(
        operation_description="Refresh JWT access token"
    )
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

    @swagger_auto_schema(
        request_body=FCMTokenSerializer,
        responses={200: openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING),
                'fcm_token': openapi.Schema(type=openapi.TYPE_STRING)
            }
        )},
        operation_description="Update user's FCM token for push notifications"
    )
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
