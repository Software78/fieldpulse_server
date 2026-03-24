import logging
from datetime import datetime
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

logger = logging.getLogger(__name__)


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
                            'status': {'type': 'string', 'enum': ['success', 'error']}
                        }
                    }
                }
            }
        }},
        summary="Batch synchronize jobs (status updates and checklist submissions)",
        description="Batch synchronize job status updates and checklist submissions. Supports both status changes and complete checklist data submissions."
    )
    def post(self, request):
        logger.info(f"Batch sync POST request received from user {request.user.id}")
        logger.info(f"Request data: {request.data}")
        
        serializer = BatchSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        batch_data = serializer.validated_data
        results = []
        total_jobs = len(batch_data['jobs'])
        success_count = 0
        error_count = 0
        
        logger.info(f"Processing {total_jobs} jobs in batch sync")
        
        for job_data in batch_data['jobs']:
            job_id = job_data['id']
            logger.debug(f"Processing job {job_id} with data: {job_data}")
            
            try:
                job = Job.objects.get(id=job_id, technician=request.user)
                logger.debug(f"Found job {job_id} for user {request.user.id}, current status: {job.status}")
            except Job.DoesNotExist:
                error_msg = f"Job {job_id} not found for user {request.user.id}"
                logger.warning(error_msg)
                error_count += 1
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
                        old_status = job.status
                        
                        if new_status in dict(Job.STATUS_CHOICES):
                            logger.info(f"Updating job {job_id} status from {old_status} to {new_status}")
                            job.status = new_status
                            job.save()
                            logger.info(f"Successfully updated job {job_id} status to {new_status}")
                        else:
                            error_msg = f"Invalid status '{new_status}' for job {job_id}. Valid choices: {dict(Job.STATUS_CHOICES).keys()}"
                            logger.error(error_msg)
                            raise ValueError(f"Invalid status: {new_status}")
                    
                    # Handle checklist update if provided
                    if 'checklist' in job_data and job_data['checklist'] is not None:
                        checklist_data = job_data['checklist']
                        logger.info(f"Processing checklist update for job {job_id}")
                        
                        # Extract relevant fields
                        data = checklist_data.get('data', {})
                        is_complete = checklist_data.get('is_complete', False)
                        client_modified_at = checklist_data.get('client_modified_at')
                        force = checklist_data.get('force', False)
                        
                        # Process data to extract UUIDs from image objects
                        processed_data = self._process_checklist_data(data)
                        
                        # Parse client_modified_at if provided
                        if client_modified_at:
                            try:
                                if isinstance(client_modified_at, str):
                                    client_modified_at = datetime.fromisoformat(client_modified_at.replace('Z', '+00:00'))
                            except ValueError as e:
                                logger.warning(f"Invalid client_modified_at format for job {job_id}: {e}")
                                client_modified_at = None
                        
                        # Check for conflicts if not forcing
                        if not force:
                            try:
                                existing_response = ChecklistResponse.objects.get(job=job)
                                conflict = detect_conflict(existing_response, client_modified_at)
                                if conflict:
                                    error_msg = f"Conflict detected for job {job_id}: Server data was modified after client's last sync"
                                    logger.warning(error_msg)
                                    raise ValueError(error_msg)
                            except ChecklistResponse.DoesNotExist:
                                # No existing response, no conflict
                                pass
                        
                        # Create or update checklist response
                        checklist_response, created = ChecklistResponse.objects.update_or_create(
                            job=job,
                            defaults={
                                'data': processed_data,
                                'is_complete': is_complete,
                                'client_modified_at': client_modified_at or timezone.now(),
                                'completed_at': timezone.now() if is_complete else None
                            }
                        )
                        
                        action = "created" if created else "updated"
                        logger.info(f"Successfully {action} checklist response for job {job_id}")
                
                job_result["status"] = "success"
                results.append(job_result)
                success_count += 1
                logger.info(f"Successfully processed job {job_id}")
                
            except Exception as e:
                error_msg = f"Error processing job {job_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                error_count += 1
                job_result.update({
                    "status": "error",
                    "message": str(e)
                })
                results.append(job_result)
        
        logger.info(f"Batch sync completed: {success_count} successful, {error_count} errors out of {total_jobs} jobs")
        logger.debug(f"Final results: {results}")
        
        return Response({"results": results}, status=status.HTTP_200_OK)
    
    def _process_checklist_data(self, data):
        """
        Process checklist data to extract UUIDs from image objects.
        
        Client sends images as objects with 'id' and 'url' fields:
        {
            "customer_signature": {"id": "uuid", "url": "http://minio/..."},
            "work_area_photo": [{"id": "uuid", "url": "http://minio/..."}]
        }
        
        We need to extract just the UUIDs for storage:
        {
            "customer_signature": "uuid",
            "work_area_photo": ["uuid"]
        }
        """
        if not isinstance(data, dict):
            return data
        
        processed_data = data.copy()
        
        # Handle customer_signature (object with id field)
        if 'customer_signature' in processed_data:
            signature_data = processed_data['customer_signature']
            if isinstance(signature_data, dict) and 'id' in signature_data:
                processed_data['customer_signature'] = signature_data['id']
        
        # Handle work_area_photo (list of objects with id fields)
        if 'work_area_photo' in processed_data and isinstance(processed_data['work_area_photo'], list):
            photo_ids = []
            for photo_item in processed_data['work_area_photo']:
                if isinstance(photo_item, dict) and 'id' in photo_item:
                    photo_ids.append(photo_item['id'])
                else:
                    # Keep as-is if it's already a UUID string
                    photo_ids.append(photo_item)
            processed_data['work_area_photo'] = photo_ids
        
        return processed_data
