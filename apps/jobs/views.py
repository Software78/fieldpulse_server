from rest_framework import generics, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import Job, ChecklistResponse
from .serializers import JobListSerializer, JobDetailSerializer, JobStatusSerializer, ChecklistSubmitSerializer, ChecklistResponseSerializer
from .pagination import JobCursorPagination
from .filters import JobFilter
from .permissions import IsTechnicianOwner
from ..sync.conflict import detect_conflict, build_conflict_response


class JobListView(generics.ListAPIView):
    """
    GET /api/jobs/
    Returns only jobs assigned to request.user (technician=request.user)
    Applies cursor pagination and filters
    Jobs sorted by scheduled_start ascending, overdue jobs first
    """
    serializer_class = JobListSerializer
    pagination_class = JobCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = JobFilter
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter jobs for the authenticated technician and sort properly
        """
        queryset = Job.objects.filter(technician=self.request.user)
        
        # Sort by scheduled_start, overdue jobs will be handled by serializer
        queryset = queryset.order_by('scheduled_start')
        
        return queryset


class JobDetailView(generics.RetrieveAPIView):
    """
    GET /api/jobs/{id}/
    Returns full detail including checklist_schema
    Returns 404 if job doesn't belong to user
    """
    serializer_class = JobDetailSerializer
    permission_classes = [IsAuthenticated, IsTechnicianOwner]
    
    def get_queryset(self):
        return Job.objects.filter(technician=self.request.user)


class JobStatusView(generics.UpdateAPIView):
    """
    PATCH /api/jobs/{id}/status/
    Only accepts the status field
    Validates status transitions
    Updates server_updated_at automatically (auto_now handles this)
    """
    serializer_class = JobStatusSerializer
    permission_classes = [IsAuthenticated, IsTechnicianOwner]
    
    def get_queryset(self):
        return Job.objects.filter(technician=self.request.user)
    
    def patch(self, request, *args, **kwargs):
        """
        Only allow PATCH requests for status updates
        """
        job = self.get_object()
        
        # Validate that only status field is being updated
        if len(request.data) != 1 or 'status' not in request.data:
            return Response(
                {'detail': 'Only status field is allowed for this endpoint'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().patch(request, *args, **kwargs)


class ChecklistView(generics.GenericAPIView):
    """
    GET + POST /api/jobs/{id}/checklist/
    Handles checklist submission and retrieval with conflict detection
    """
    permission_classes = [IsAuthenticated, IsTechnicianOwner]
    
    def get_queryset(self):
        return Job.objects.filter(technician=self.request.user)
    
    def get(self, request, *args, **kwargs):
        """Returns the existing ChecklistResponse for the job, or 404 if none"""
        job = self.get_object()
        
        try:
            response = job.checklist_response
            serializer = ChecklistResponseSerializer(response)
            return Response(serializer.data)
        except ChecklistResponse.DoesNotExist:
            return Response(
                {"detail": "No checklist response found for this job"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def post(self, request, *args, **kwargs):
        """Creates or updates the ChecklistResponse with conflict detection"""
        job = self.get_object()
        
        # Validate incoming data
        serializer = ChecklistSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        force_override = data.get('force', False)
        
        try:
            # Try to get existing response
            existing_response = job.checklist_response
            
            # Check for conflict unless force override is requested
            if not force_override and detect_conflict(existing_response, data.get('client_modified_at')):
                # Conflict detected
                conflict_payload = build_conflict_response(data, existing_response)
                return Response({
                    "error": "conflict",
                    "message": "Job was modified on the server while you were offline.",
                    **conflict_payload
                }, status=status.HTTP_409_CONFLICT)
            
            # Update existing response
            existing_response.data = data['data']
            existing_response.is_complete = data['is_complete']
            existing_response.client_modified_at = data.get('client_modified_at')
            
            # Handle completion
            if data['is_complete'] and not existing_response.completed_at:
                existing_response.completed_at = timezone.now()
                job.status = 'completed'
                job.save()
            
            existing_response.save()
            
            # Return updated response
            response_serializer = ChecklistResponseSerializer(existing_response)
            return Response(response_serializer.data)
            
        except ChecklistResponse.DoesNotExist:
            # Create new response
            new_response = ChecklistResponse.objects.create(
                job=job,
                data=data['data'],
                is_complete=data['is_complete'],
                client_modified_at=data.get('client_modified_at')
            )
            
            # Handle completion
            if data['is_complete']:
                new_response.completed_at = timezone.now()
                new_response.save()
                job.status = 'completed'
                job.save()
            
            response_serializer = ChecklistResponseSerializer(new_response)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
