"""
Views for media uploads (photos and signatures).
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import ValidationError
from botocore.exceptions import ClientError, NoCredentialsError

from .storage import storage
from .serializers import PhotoUploadSerializer, SignatureUploadSerializer

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def photo_upload_view(request):
    """
    Upload a photo to MinIO storage.
    
    POST /api/media/photos/
    Content-Type: multipart/form-data
    
    Required fields:
    - job_id: UUID of the job
    - field_id: Field identifier from checklist
    - file: Image file (max 10MB)
    - captured_at: ISO datetime string
    
    Optional fields:
    - latitude: Decimal (-90 to 90)
    - longitude: Decimal (-180 to 180)
    
    Returns:
    {
        "id": "uuid",
        "url": "https://minio-endpoint/bucket/photos/job_id/field_id/uuid.jpg"
    }
    """
    try:
        serializer = PhotoUploadSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Get the validated data
            validated_data = serializer.validated_data
            file_obj = validated_data['file']
            s3_key = validated_data['s3_key']
            
            # Determine content type from file
            content_type = getattr(file_obj, 'content_type', 'image/jpeg')
            
            try:
                # Upload to MinIO
                s3_url = storage.upload_file(file_obj, s3_key, content_type)
                
                # Update the instance with the S3 URL
                validated_data['s3_url'] = s3_url
                photo_upload = serializer.save()
                
                logger.info(f"Successfully uploaded photo {photo_upload.id} for job {photo_upload.job.id}")
                
                return Response({
                    'id': str(photo_upload.id),
                    'url': s3_url
                }, status=status.HTTP_201_CREATED)
                
            except (ClientError, NoCredentialsError) as e:
                logger.error(f"Failed to upload photo to MinIO: {e}")
                return Response(
                    {'error': 'Failed to upload file to storage.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception as e:
                logger.error(f"Unexpected error during photo upload: {e}")
                return Response(
                    {'error': 'An unexpected error occurred during upload.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Unexpected error in photo_upload_view: {e}")
        return Response(
            {'error': 'An unexpected error occurred.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def signature_upload_view(request):
    """
    Upload a signature to MinIO storage.
    
    POST /api/media/signatures/
    Content-Type: multipart/form-data
    
    Required fields:
    - job_id: UUID of the job
    - field_id: Field identifier from checklist
    - file: PNG file (max 5MB)
    - captured_at: ISO datetime string
    
    Returns:
    {
        "id": "uuid",
        "url": "https://minio-endpoint/bucket/signatures/job_id/field_id/uuid.png"
    }
    """
    try:
        serializer = SignatureUploadSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            # Get the validated data
            validated_data = serializer.validated_data
            file_obj = validated_data['file']
            s3_key = validated_data['s3_key']
            
            # Signatures should always be PNG
            content_type = 'image/png'
            
            try:
                # Upload to MinIO
                s3_url = storage.upload_file(file_obj, s3_key, content_type)
                
                # Update the instance with the S3 URL
                validated_data['s3_url'] = s3_url
                signature_upload = serializer.save()
                
                logger.info(f"Successfully uploaded signature {signature_upload.id} for job {signature_upload.job.id}")
                
                return Response({
                    'id': str(signature_upload.id),
                    'url': s3_url
                }, status=status.HTTP_201_CREATED)
                
            except (ClientError, NoCredentialsError) as e:
                logger.error(f"Failed to upload signature to MinIO: {e}")
                return Response(
                    {'error': 'Failed to upload file to storage.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            except Exception as e:
                logger.error(f"Unexpected error during signature upload: {e}")
                return Response(
                    {'error': 'An unexpected error occurred during upload.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Unexpected error in signature_upload_view: {e}")
        return Response(
            {'error': 'An unexpected error occurred.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
