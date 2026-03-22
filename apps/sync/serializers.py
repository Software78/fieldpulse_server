from rest_framework import serializers
from datetime import datetime
import uuid


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
