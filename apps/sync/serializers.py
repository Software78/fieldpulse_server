from rest_framework import serializers
from datetime import datetime
import uuid
from .models import Job, ChecklistResponse


class SyncJobSerializer(serializers.ModelSerializer):
    """Lightweight job serializer for sync operations"""
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id', 'customer_name', 'customer_phone', 'address', 'latitude', 'longitude',
            'scheduled_start', 'scheduled_end', 'status', 'is_overdue', 'server_updated_at',
            'job_description', 'notes'
        ]


class SyncChecklistSerializer(serializers.ModelSerializer):
    """Checklist response serializer for sync operations"""
    job_id = serializers.UUIDField(source='job.id', read_only=True)
    
    class Meta:
        model = ChecklistResponse
        fields = [
            'job_id', 'data', 'is_complete', 'last_modified_at', 
            'client_modified_at', 'completed_at'
        ]


class SyncDataSerializer(serializers.Serializer):
    """Combined sync data serializer"""
    jobs = SyncJobSerializer(many=True, read_only=True)
    checklists = SyncChecklistSerializer(many=True, read_only=True)


class BatchChecklistSerializer(serializers.Serializer):
    data = serializers.DictField()
    client_modified_at = serializers.DateTimeField()
    is_complete = serializers.BooleanField()
    force = serializers.BooleanField(default=False)


class BatchJobUpdateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField(required=False, allow_null=True)
    checklist = BatchChecklistSerializer(required=False, allow_null=True)


class BatchSyncSerializer(serializers.Serializer):
    jobs = serializers.ListField(
        child=BatchJobUpdateSerializer(),
        max_length=50
    )
