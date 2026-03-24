from rest_framework import serializers
from datetime import datetime
import uuid
from .models import Job, ChecklistResponse, ChecklistSchema
from apps.media_app.models import PhotoUpload, SignatureUpload


class SyncJobSerializer(serializers.ModelSerializer):
    """Lightweight job serializer for sync operations"""
    is_overdue = serializers.BooleanField(read_only=True)
    checklist_schema = serializers.SerializerMethodField()
    checklist_submission = serializers.SerializerMethodField()
    
    class Meta:
        model = Job
        fields = [
            'id', 'customer_name', 'customer_phone', 'address', 'latitude', 'longitude',
            'scheduled_start', 'scheduled_end', 'status', 'is_overdue', 'server_updated_at',
            'job_description', 'notes', 'checklist_schema', 'checklist_submission'
        ]
    
    def get_checklist_schema(self, obj):
        """Get checklist schema for this job"""
        try:
            schema = obj.checklist_schema
            return {
                'fields': schema.fields.get('fields', []),
                'version': schema.version
            }
        except ChecklistSchema.DoesNotExist:
            # Return a default empty schema if none exists
            return {'fields': [], 'version': 1}
    
    def get_checklist_submission(self, obj):
        """Get checklist submission data for jobs with image URLs"""
        try:
            response = obj.checklist_response
            data = response.data.copy()  # Make a copy to avoid modifying original
            
            # Convert image UUIDs to URLs
            data = self._convert_image_uuids_to_urls(data, obj)
            
            return {
                'data': data,
                'is_complete': response.is_complete,
                'completed_at': response.completed_at,
                'last_modified_at': response.last_modified_at
            }
        except ChecklistResponse.DoesNotExist:
            return None
    
    def _convert_image_uuids_to_urls(self, data, job):
        """Convert image UUIDs in checklist data to their proxy URLs"""
        if not isinstance(data, dict):
            return data
        
        converted_data = data.copy()
        
        # Handle customer_signature (single UUID)
        if 'customer_signature' in converted_data and converted_data['customer_signature']:
            signature_uuid = converted_data['customer_signature']
            try:
                signature = SignatureUpload.objects.get(id=signature_uuid, job=job)
                # Return proxy URL instead of direct S3 URL
                converted_data['customer_signature'] = f"/api/media/signatures/{signature_uuid}/"
            except (SignatureUpload.DoesNotExist, ValueError):
                # Keep original UUID if not found or invalid
                pass
        
        # Handle work_area_photo (list of UUIDs)
        if 'work_area_photo' in converted_data and isinstance(converted_data['work_area_photo'], list):
            photo_urls = []
            for photo_uuid in converted_data['work_area_photo']:
                try:
                    photo = PhotoUpload.objects.get(id=photo_uuid, job=job)
                    # Return proxy URL instead of direct S3 URL
                    photo_urls.append(f"/api/media/photos/{photo_uuid}/")
                except (PhotoUpload.DoesNotExist, ValueError):
                    # Keep original UUID if not found or invalid
                    photo_urls.append(photo_uuid)
            converted_data['work_area_photo'] = photo_urls
        
        return converted_data


class SyncChecklistSerializer(serializers.ModelSerializer):
    """Checklist response serializer for sync operations"""
    job_id = serializers.UUIDField(source='job.id', read_only=True)
    data = serializers.SerializerMethodField()
    
    class Meta:
        model = ChecklistResponse
        fields = [
            'job_id', 'data', 'is_complete', 'last_modified_at', 
            'client_modified_at', 'completed_at'
        ]
    
    def get_data(self, obj):
        """Get checklist data with image proxy URLs"""
        data = obj.data.copy()
        job = obj.job
        
        # Convert image UUIDs to proxy URLs
        if isinstance(data, dict):
            converted_data = data.copy()
            
            # Handle customer_signature (single UUID)
            if 'customer_signature' in converted_data and converted_data['customer_signature']:
                signature_uuid = converted_data['customer_signature']
                try:
                    signature = SignatureUpload.objects.get(id=signature_uuid, job=job)
                    # Return proxy URL instead of direct S3 URL
                    converted_data['customer_signature'] = f"/api/media/signatures/{signature_uuid}/"
                except (SignatureUpload.DoesNotExist, ValueError):
                    # Keep original UUID if not found or invalid
                    pass
            
            # Handle work_area_photo (list of UUIDs)
            if 'work_area_photo' in converted_data and isinstance(converted_data['work_area_photo'], list):
                photo_urls = []
                for photo_uuid in converted_data['work_area_photo']:
                    try:
                        photo = PhotoUpload.objects.get(id=photo_uuid, job=job)
                        # Return proxy URL instead of direct S3 URL
                        photo_urls.append(f"/api/media/photos/{photo_uuid}/")
                    except (PhotoUpload.DoesNotExist, ValueError):
                        # Keep original UUID if not found or invalid
                        photo_urls.append(photo_uuid)
                converted_data['work_area_photo'] = photo_urls
            
            return converted_data
        
        return data


class SyncDataSerializer(serializers.Serializer):
    """Combined sync data serializer"""
    jobs = SyncJobSerializer(many=True, read_only=True)
    checklists = SyncChecklistSerializer(many=True, read_only=True)


class BatchJobUpdateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField(required=False, allow_null=True)
    checklist = serializers.DictField(required=False, allow_null=True)


class BatchSyncSerializer(serializers.Serializer):
    jobs = serializers.ListField(
        child=BatchJobUpdateSerializer(),
        max_length=50
    )
