from rest_framework import serializers
from .models import Job, ChecklistSchema, ChecklistResponse


class JobListSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id', 'customer_name', 'customer_phone', 'address', 'latitude', 'longitude',
            'scheduled_start', 'scheduled_end', 'status', 'is_overdue', 'server_updated_at'
        ]


class ChecklistSchemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistSchema
        fields = ['fields', 'version']


class JobDetailSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)
    checklist_schema = ChecklistSchemaSerializer(read_only=True)
    
    class Meta:
        model = Job
        fields = [
            'id', 'customer_name', 'customer_phone', 'address', 'latitude', 'longitude',
            'scheduled_start', 'scheduled_end', 'status', 'is_overdue', 'server_updated_at',
            'job_description', 'notes', 'checklist_schema'
        ]


class JobStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ['status']
    
    def validate_status(self, value):
        """
        Validate status transitions:
        - pending → in_progress
        - in_progress → completed
        """
        if not self.instance:
            raise serializers.ValidationError("Job instance required for status update")
        
        current_status = self.instance.status
        valid_transitions = {
            'pending': ['in_progress'],
            'in_progress': ['completed'],
            'completed': []  # No transitions allowed from completed
        }
        
        if value not in valid_transitions.get(current_status, []):
            if current_status == 'pending' and value == 'completed':
                raise serializers.ValidationError(
                    "Cannot mark job as completed directly. First set status to 'in_progress'."
                )
            elif current_status == 'completed':
                raise serializers.ValidationError(
                    "Cannot change status of a completed job."
                )
            else:
                raise serializers.ValidationError(
                    f"Invalid status transition from {current_status} to {value}. "
                    f"Allowed transitions from {current_status}: {', '.join(valid_transitions.get(current_status, []))}"
                )
        
        return value


class ChecklistSubmitSerializer(serializers.ModelSerializer):
    """
    Validates incoming checklist data for submission
    """
    force = serializers.BooleanField(default=False, help_text="Force override conflicts")
    
    class Meta:
        model = ChecklistResponse
        fields = ['data', 'client_modified_at', 'is_complete', 'force']
        
    def validate_data(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Data must be a dictionary")
        return value


class ChecklistResponseSerializer(serializers.ModelSerializer):
    """
    For reading back a saved response
    """
    class Meta:
        model = ChecklistResponse
        fields = ['data', 'is_complete', 'last_modified_at', 'client_modified_at', 'completed_at']
