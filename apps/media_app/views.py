"""
Views for media uploads (photos and signatures).
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.core.exceptions import ValidationError
from django.http import HttpResponse, Http404
from botocore.exceptions import ClientError, NoCredentialsError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .storage import storage
from .serializers import PhotoUploadSerializer, SignatureUploadSerializer
from .models import PhotoUpload, SignatureUpload

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
@extend_schema(
    summary="Upload a photo to MinIO storage",
    description="Upload a photo file associated with a specific job and checklist field",
    request=PhotoUploadSerializer,
    responses={201: {
        'type': 'object',
        'properties': {
            'id': {'type': 'string', 'format': 'uuid'},
            'url': {'type': 'string', 'format': 'uri'}
        }
    }},
    examples=[
        OpenApiExample(
            'Photo Upload Example',
            summary='Example request for photo upload',
            value={
                'job_id': '550e8400-e29b-41d4-a716-446655440000',
                'field_id': 'customer_photo',
                'file': 'image.jpg',
                'captured_at': '2024-01-15T10:30:00Z',
                'latitude': 40.7128,
                'longitude': -74.0060
            }
        )
    ]
)
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
        "url": "/api/media/photos/{uuid}/"
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
            
            # Determine content type from file
            content_type = getattr(file_obj, 'content_type', 'image/jpeg')
            
            try:
                # Create the upload instance (this generates s3_key)
                photo_upload = serializer.save()
                
                # Upload to MinIO using the generated s3_key
                s3_url = storage.upload_file(file_obj, photo_upload.s3_key, content_type)
                
                # Update the instance with the S3 URL
                photo_upload.s3_url = s3_url
                photo_upload.save()
                
                logger.info(f"Successfully uploaded photo {photo_upload.id} for job {photo_upload.job.id}")
                
                return Response({
                    'id': str(photo_upload.id),
                    'url': f'/api/media/photos/{photo_upload.id}/'
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
@extend_schema(
    summary="Upload a signature to MinIO storage",
    description="Upload a PNG signature file associated with a specific job and checklist field",
    request=SignatureUploadSerializer,
    responses={201: {
        'type': 'object',
        'properties': {
            'id': {'type': 'string', 'format': 'uuid'},
            'url': {'type': 'string', 'format': 'uri'}
        }
    }},
    examples=[
        OpenApiExample(
            'Signature Upload Example',
            summary='Example request for signature upload',
            value={
                'job_id': '550e8400-e29b-41d4-a716-446655440000',
                'field_id': 'customer_signature',
                'file': 'signature.png',
                'captured_at': '2024-01-15T10:30:00Z'
            }
        )
    ]
)
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
        "url": "/api/media/signatures/{uuid}/"
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
            
            # Signatures should always be PNG
            content_type = 'image/png'
            
            try:
                # Create the upload instance (this generates s3_key)
                signature_upload = serializer.save()
                
                # Upload to MinIO using the generated s3_key
                s3_url = storage.upload_file(file_obj, signature_upload.s3_key, content_type)
                
                # Update the instance with the S3 URL
                signature_upload.s3_url = s3_url
                signature_upload.save()
                
                logger.info(f"Successfully uploaded signature {signature_upload.id} for job {signature_upload.job.id}")
                
                return Response({
                    'id': str(signature_upload.id),
                    'url': f'/api/media/signatures/{signature_upload.id}/'
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    summary="Get photo by ID",
    description="Serve a photo file through Django proxy",
    responses={200: {'type': 'string', 'format': 'binary'}}
)
def photo_proxy_view(request, photo_id):
    """
    Proxy endpoint to serve photos through Django instead of direct MinIO URLs.
    
    GET /api/media/photos/{photo_id}/
    
    Returns the photo file as binary data with proper content type.
    """
    try:
        photo = PhotoUpload.objects.get(id=photo_id)
        
        # Check if user has access to this photo (belongs to their job or is admin)
        if not (request.user.is_staff or photo.job.technician == request.user):
            return Response(
                {'error': 'Permission denied.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get file from MinIO
        file_obj = storage.get_file(photo.s3_key)
        
        # Determine content type
        content_type = 'image/jpeg'  # Default
        if photo.s3_key.lower().endswith('.png'):
            content_type = 'image/png'
        elif photo.s3_key.lower().endswith('.jpg') or photo.s3_key.lower().endswith('.jpeg'):
            content_type = 'image/jpeg'
        
        # Return file as response
        response = HttpResponse(file_obj, content_type=content_type)
        response['Cache-Control'] = 'public, max-age=86400'  # Cache for 1 day
        return response
        
    except PhotoUpload.DoesNotExist:
        raise Http404("Photo not found")
    except (ClientError, NoCredentialsError) as e:
        logger.error(f"Failed to retrieve photo {photo_id} from MinIO: {e}")
        return Response(
            {'error': 'Failed to retrieve file.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f"Unexpected error in photo_proxy_view: {e}")
        return Response(
            {'error': 'An unexpected error occurred.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@extend_schema(
    summary="Get signature by ID",
    description="Serve a signature file through Django proxy",
    responses={200: {'type': 'string', 'format': 'binary'}}
)
def signature_proxy_view(request, signature_id):
    """
    Proxy endpoint to serve signatures through Django instead of direct MinIO URLs.
    
    GET /api/media/signatures/{signature_id}/
    
    Returns the signature file as binary data with proper content type.
    """
    try:
        signature = SignatureUpload.objects.get(id=signature_id)
        
        # Check if user has access to this signature (belongs to their job or is admin)
        if not (request.user.is_staff or signature.job.technician == request.user):
            return Response(
                {'error': 'Permission denied.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get file from MinIO
        file_obj = storage.get_file(signature.s3_key)
        
        # Return file as response
        response = HttpResponse(file_obj, content_type='image/png')
        response['Cache-Control'] = 'public, max-age=86400'  # Cache for 1 day
        return response
        
    except SignatureUpload.DoesNotExist:
        raise Http404("Signature not found")
    except (ClientError, NoCredentialsError) as e:
        logger.error(f"Failed to retrieve signature {signature_id} from MinIO: {e}")
        return Response(
            {'error': 'Failed to retrieve file.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f"Unexpected error in signature_proxy_view: {e}")
        return Response(
            {'error': 'An unexpected error occurred.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
