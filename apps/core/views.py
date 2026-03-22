"""
Core views for fieldpulse project.
"""
import logging
from django.http import JsonResponse
from django.db import connection
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from botocore.exceptions import ClientError
import boto3

logger = logging.getLogger(__name__)


class HealthCheckView(APIView):
    """
    Health check endpoint that returns system status.
    
    Returns:
    {
        "status": "ok",
        "database": "ok",
        "storage": "ok"
    }
    """
    
    permission_classes = []  # No authentication required
    
    def get(self, request):
        health_status = {
            "status": "ok",
            "database": "ok",
            "storage": "ok"
        }
        
        # Check database connectivity
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status["database"] = "error"
            health_status["status"] = "error"
        
        # Check storage (MinIO/S3) connectivity
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=settings.AWS_S3_ENDPOINT_URL,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            # Try to list buckets to verify connectivity
            s3_client.list_buckets()
        except (ClientError, Exception) as e:
            logger.error(f"Storage health check failed: {e}")
            health_status["storage"] = "error"
            health_status["status"] = "error"
        
        status_code = 200 if health_status["status"] == "ok" else 503
        return Response(health_status, status=status_code)


def simple_health_check(request):
    """Simple health check endpoint for load balancers."""
    return JsonResponse({"status": "ok"})
