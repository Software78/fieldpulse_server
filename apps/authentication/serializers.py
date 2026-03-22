"""
Serializers for authentication app.
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login with email and password.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                username=email,
                password=password
            )
            
            if not user:
                raise serializers.ValidationError({
                    'error': 'invalid_credentials',
                    'message': 'Invalid email or password.',
                    'details': {}
                })
            
            if not user.is_active:
                raise serializers.ValidationError({
                    'error': 'account_disabled',
                    'message': 'Your account has been disabled.',
                    'details': {}
                })
            
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError({
                'error': 'missing_fields',
                'message': 'Both email and password are required.',
                'details': {}
            })


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile information.
    """
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone']
        read_only_fields = ['id']


class TokenResponseSerializer(serializers.Serializer):
    """
    Serializer for token response with user information.
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class FCMTokenSerializer(serializers.Serializer):
    """
    Serializer for updating FCM token.
    """
    fcm_token = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_fcm_token(self, value):
        """Validate FCM token format if provided."""
        if value and len(value) > 255:
            raise serializers.ValidationError("FCM token is too long.")
        return value
