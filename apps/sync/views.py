from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from .models import Job, ChecklistResponse
from .pagination import JobCursorPagination
from .filters import JobFilter
from .serializers import BatchSyncSerializer, SyncDataSerializer
from .conflict import detect_conflict, build_conflict_response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter


class BatchSyncView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = JobCursorPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = JobFilter

    def get_queryset(self):
        """Get jobs for the authenticated user"""
        return Job.objects.filter(technician=self.request.user)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='last_sync_time',
                description='ISO 8601 datetime string for last sync timestamp (optional)',
                required=False,
                type=str,
                location='query'
            ),
            OpenApiParameter(
                name='cursor',
                description='Pagination cursor',
                required=False,
                type=str,
                location='query'
            ),
            OpenApiParameter(
                name='page_size',
                description='Number of results per page',
                required=False,
                type=int,
                location='query'
            )
        ],
        responses={200: SyncDataSerializer},
        summary="Get jobs and checklists updated since last sync",
        description="Retrieve paginated jobs and checklist responses that have been updated since the specified timestamp. If no timestamp is provided, returns all records."
    )
    def get(self, request):
        """Get jobs and checklists updated since last_sync_time"""
        last_sync_time = request.query_params.get('last_sync_time')
        
        if last_sync_time:
            try:
                # Parse the timestamp
                from datetime import datetime
                sync_time = datetime.fromisoformat(last_sync_time.replace('Z', '+00:00'))
            except ValueError:
                return Response(
                    {'detail': 'Invalid datetime format. Use ISO 8601 format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # If no sync time provided, use a very early date to get all records
            from datetime import datetime, timezone
            sync_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
        
        # Get updated jobs
        jobs_queryset = self.get_queryset().filter(server_updated_at__gte=sync_time)
        jobs = jobs_queryset.order_by('server_updated_at')
        
        # Get updated checklist responses
        checklists_queryset = ChecklistResponse.objects.filter(
            job__technician=request.user,
            last_modified_at__gte=sync_time
        ).order_by('last_modified_at')
        
        # Apply pagination
        paginator = self.pagination_class()
        paginated_jobs = paginator.paginate_queryset(jobs, request)
        
        # Serialize data
        from .serializers import SyncJobSerializer, SyncChecklistSerializer
        job_serializer = SyncJobSerializer(paginated_jobs, many=True)
        checklist_serializer = SyncChecklistSerializer(checklists_queryset, many=True)
        
        # Combine results
        sync_data = {
            'jobs': job_serializer.data,
            'checklists': checklist_serializer.data
        }
        
        # Return paginated response
        return paginator.get_paginated_response(sync_data)

    @extend_schema(
        request=BatchSyncSerializer,
        responses={200: {
            'type': 'object',
            'properties': {
                'results': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string'},
                            'status': {'type': 'string', 'enum': ['success', 'error', 'conflict']}
                        }
                    }
                }
            }
        }},
        summary="Batch synchronize jobs and checklists",
        description="Batch synchronize jobs and checklists with conflict detection"
    )
    def post(self, request):
        serializer = BatchSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        batch_data = serializer.validated_data
        results = []
        
        for job_data in batch_data['jobs']:
            job_id = job_data['id']
            
            try:
                job = Job.objects.get(id=job_id, technician=request.user)
            except Job.DoesNotExist:
                results.append({
                    "id": str(job_id),
                    "status": "error",
                    "message": "Job not found"
                })
                continue
            
            job_result = {"id": str(job_id)}
            
            try:
                with transaction.atomic():
                    # Handle status update if provided
                    if 'status' in job_data and job_data['status'] is not None:
                        new_status = job_data['status']
                        if new_status in dict(Job.STATUS_CHOICES):
                            job.status = new_status
                            job.save()
                    
                    # Handle checklist update if provided
                    if 'checklist' in job_data and job_data['checklist'] is not None:
                        checklist_data = job_data['checklist']
                        
                        # Get or create checklist response
                        checklist_response, created = ChecklistResponse.objects.get_or_create(
                            job=job,
                            defaults={
                                'data': checklist_data['data'],
                                'is_complete': checklist_data['is_complete'],
                                'client_modified_at': checklist_data['client_modified_at']
                            }
                        )
                        
                        if not created:
                            # Check for conflicts
                            has_conflict = detect_conflict(
                                checklist_response, 
                                checklist_data['client_modified_at']
                            )
                            
                            if has_conflict and not checklist_data['force']:
                                # Return conflict response
                                conflict_info = build_conflict_response(
                                    checklist_data, 
                                    checklist_response
                                )
                                job_result.update({
                                    "status": "conflict",
                                    **conflict_info
                                })
                                results.append(job_result)
                                continue
                        
                        # Save checklist data
                        checklist_response.data = checklist_data['data']
                        checklist_response.is_complete = checklist_data['is_complete']
                        checklist_response.client_modified_at = checklist_data['client_modified_at']
                        
                        if checklist_data['is_complete'] and not checklist_response.completed_at:
                            checklist_response.completed_at = timezone.now()
                        
                        checklist_response.save()
                
                job_result["status"] = "success"
                results.append(job_result)
                
            except Exception as e:
                job_result.update({
                    "status": "error",
                    "message": str(e)
                })
                results.append(job_result)
        
        return Response({"results": results}, status=status.HTTP_200_OK)
