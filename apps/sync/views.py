from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from apps.jobs.models import Job, ChecklistResponse
from .serializers import BatchSyncSerializer
from .conflict import detect_conflict, build_conflict_response


class BatchSyncView(APIView):
    permission_classes = [IsAuthenticated]

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
