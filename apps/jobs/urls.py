"""
URLs for jobs app.
"""
from django.urls import path
from .views import JobListView, JobDetailView, JobStatusView, ChecklistView

app_name = 'jobs'

urlpatterns = [
    path('', JobListView.as_view(), name='job-list'),
    path('<uuid:pk>/', JobDetailView.as_view(), name='job-detail'),
    path('<uuid:pk>/status/', JobStatusView.as_view(), name='job-status'),
    path('<uuid:pk>/checklist/', ChecklistView.as_view(), name='job-checklist'),
]
