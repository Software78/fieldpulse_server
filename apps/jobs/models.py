import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Job(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='jobs'
    )
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=20)
    address = models.TextField()
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    job_description = models.TextField()
    notes = models.TextField(blank=True)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    server_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer_name} - {self.scheduled_start.strftime('%Y-%m-%d %H:%M')}"

    @property
    def is_overdue(self):
        """
        Returns True if status is 'pending' or 'in_progress' and scheduled_end is in the past.
        """
        if self.status in ['pending', 'in_progress']:
            return self.scheduled_end < timezone.now()
        return False


class ChecklistSchema(models.Model):
    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE,
        related_name='checklist_schema'
    )
    fields = models.JSONField(help_text="Stores the dynamic form definition")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-version']

    def __str__(self):
        return f"Checklist Schema for {self.job.id} (v{self.version})"


class ChecklistResponse(models.Model):
    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE,
        related_name='checklist_response'
    )
    data = models.JSONField(default=dict, help_text="Maps field_id to value")
    is_complete = models.BooleanField(default=False)
    last_modified_at = models.DateTimeField(auto_now=True)
    client_modified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Sent by client, for conflict detection"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-last_modified_at']

    def __str__(self):
        return f"Checklist Response for {self.job.id} ({'Complete' if self.is_complete else 'Incomplete'})"
