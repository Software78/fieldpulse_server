"""
Models for media uploads (photos and signatures).
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from apps.sync.models import Job


class PhotoUpload(models.Model):
    """
    Model for storing photo upload information.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='photo_uploads'
    )
    field_id = models.CharField(max_length=50, help_text="Field identifier from checklist")
    s3_key = models.CharField(max_length=500, help_text="S3 object key")
    s3_url = models.URLField(max_length=1000, help_text="Public URL of the uploaded photo")
    captured_at = models.DateTimeField(help_text="When the photo was captured")
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS latitude where photo was captured"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS longitude where photo was captured"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="When the photo was uploaded to server")

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['job', 'field_id']),
            models.Index(fields=['uploaded_at']),
        ]

    def __str__(self):
        return f"Photo {self.id} for job {self.job.id} - field {self.field_id}"


class SignatureUpload(models.Model):
    """
    Model for storing signature upload information.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='signature_uploads'
    )
    field_id = models.CharField(max_length=50, help_text="Field identifier from checklist")
    s3_key = models.CharField(max_length=500, help_text="S3 object key")
    s3_url = models.URLField(max_length=1000, help_text="Public URL of the uploaded signature")
    captured_at = models.DateTimeField(help_text="When the signature was captured")
    uploaded_at = models.DateTimeField(auto_now_add=True, help_text="When the signature was uploaded to server")

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['job', 'field_id']),
            models.Index(fields=['uploaded_at']),
        ]

    def __str__(self):
        return f"Signature {self.id} for job {self.job.id} - field {self.field_id}"
