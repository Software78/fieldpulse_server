"""
Serializers for media uploads.
"""
import uuid
from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from apps.jobs.models import Job
from .models import PhotoUpload, SignatureUpload


class PhotoUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for photo uploads.
    """
    job_id = serializers.UUIDField(write_only=True)
    file = serializers.ImageField(
        max_length=100,
        allow_empty_file=False,
        error_messages={
            'invalid_image': 'Upload a valid image file.',
            'empty_image': 'The uploaded file is empty.',
        }
    )
    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        error_messages={
            'invalid': 'Enter a valid decimal number.',
            'max_digits': 'Ensure there are no more than 9 digits in total.',
            'max_decimal_places': 'Ensure there are no more than 6 decimal places.',
            'max_whole_digits': 'Ensure there are no more than 3 digits before the decimal point.',
        }
    )
    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
        error_messages={
            'invalid': 'Enter a valid decimal number.',
            'max_digits': 'Ensure there are no more than 9 digits in total.',
            'max_decimal_places': 'Ensure there are no more than 6 decimal places.',
            'max_whole_digits': 'Ensure there are no more than 3 digits before the decimal point.',
        }
    )

    class Meta:
        model = PhotoUpload
        fields = [
            'id', 'job_id', 'field_id', 'file', 'captured_at', 
            'latitude', 'longitude', 's3_key', 's3_url', 'uploaded_at'
        ]
        read_only_fields = ['id', 's3_key', 's3_url', 'uploaded_at']

    def validate_job_id(self, value):
        """
        Validate that the job exists and belongs to the requesting user.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError('Authentication required.')
        
        try:
            job = Job.objects.get(id=value, technician=request.user)
        except Job.DoesNotExist:
            raise serializers.ValidationError('Job not found or does not belong to you.')
        
        return job

    def validate_file(self, value):
        """
        Validate the uploaded file.
        """
        if not value:
            raise serializers.ValidationError('File is required.')
        
        # Check file size (10MB max)
        if hasattr(value, 'size') and value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError('File size cannot exceed 10MB.')
        
        # Check if it's actually an image (additional validation)
        if not getattr(value, 'content_type', '').startswith('image/'):
            raise serializers.ValidationError('File must be an image.')
        
        return value

    def validate_captured_at(self, value):
        """
        Validate the captured_at timestamp.
        """
        if value > timezone.now():
            raise serializers.ValidationError('Capture time cannot be in the future.')
        
        # Optional: Don't allow photos captured too long ago (e.g., more than 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        if value < thirty_days_ago:
            raise serializers.ValidationError('Capture time cannot be more than 30 days ago.')
        
        return value

    def validate(self, attrs):
        """
        Validate the entire data.
        """
        # If latitude is provided, longitude should also be provided and vice versa
        latitude = attrs.get('latitude')
        longitude = attrs.get('longitude')
        
        if (latitude is not None and longitude is None) or (latitude is None and longitude is not None):
            raise serializers.ValidationError(
                'Both latitude and longitude must be provided together.'
            )
        
        # Validate coordinate ranges
        if latitude is not None:
            try:
                lat_float = float(latitude)
                if not (-90 <= lat_float <= 90):
                    raise serializers.ValidationError('Latitude must be between -90 and 90.')
            except (ValueError, TypeError):
                raise serializers.ValidationError('Invalid latitude value.')
        
        if longitude is not None:
            try:
                lon_float = float(longitude)
                if not (-180 <= lon_float <= 180):
                    raise serializers.ValidationError('Longitude must be between -180 and 180.')
            except (ValueError, TypeError):
                raise serializers.ValidationError('Invalid longitude value.')
        
        return attrs

    def create(self, validated_data):
        """
        Create a PhotoUpload instance.
        """
        job = validated_data.pop('job_id')  # This is the Job instance from validate_job_id
        file_obj = validated_data.pop('file')
        
        # Generate unique S3 key
        file_uuid = uuid.uuid4()
        s3_key = f"photos/{job.id}/{validated_data['field_id']}/{file_uuid}.jpg"
        
        # Upload to MinIO (this will be done in the view)
        validated_data['job'] = job
        validated_data['s3_key'] = s3_key
        
        return super().create(validated_data)


class SignatureUploadSerializer(serializers.ModelSerializer):
    """
    Serializer for signature uploads.
    """
    job_id = serializers.UUIDField(write_only=True)
    file = serializers.ImageField(
        max_length=100,
        allow_empty_file=False,
        error_messages={
            'invalid_image': 'Upload a valid PNG image file.',
            'empty_image': 'The uploaded file is empty.',
        }
    )

    class Meta:
        model = SignatureUpload
        fields = [
            'id', 'job_id', 'field_id', 'file', 'captured_at',
            's3_key', 's3_url', 'uploaded_at'
        ]
        read_only_fields = ['id', 's3_key', 's3_url', 'uploaded_at']

    def validate_job_id(self, value):
        """
        Validate that the job exists and belongs to the requesting user.
        """
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError('Authentication required.')
        
        try:
            job = Job.objects.get(id=value, technician=request.user)
        except Job.DoesNotExist:
            raise serializers.ValidationError('Job not found or does not belong to you.')
        
        return job

    def validate_file(self, value):
        """
        Validate the uploaded signature file.
        """
        if not value:
            raise serializers.ValidationError('File is required.')
        
        # Check file size (5MB max)
        if hasattr(value, 'size') and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('File size cannot exceed 5MB.')
        
        # Check if it's a PNG file
        content_type = getattr(value, 'content_type', '')
        if content_type != 'image/png':
            raise serializers.ValidationError('Signature must be a PNG file.')
        
        return value

    def validate_captured_at(self, value):
        """
        Validate the captured_at timestamp.
        """
        if value > timezone.now():
            raise serializers.ValidationError('Capture time cannot be in the future.')
        
        # Optional: Don't allow signatures captured too long ago (e.g., more than 30 days)
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
        if value < thirty_days_ago:
            raise serializers.ValidationError('Capture time cannot be more than 30 days ago.')
        
        return value

    def create(self, validated_data):
        """
        Create a SignatureUpload instance.
        """
        job = validated_data.pop('job_id')  # This is the Job instance from validate_job_id
        file_obj = validated_data.pop('file')
        
        # Generate unique S3 key
        file_uuid = uuid.uuid4()
        s3_key = f"signatures/{job.id}/{validated_data['field_id']}/{file_uuid}.png"
        
        # Upload to MinIO (this will be done in the view)
        validated_data['job'] = job
        validated_data['s3_key'] = s3_key
        
        return super().create(validated_data)
