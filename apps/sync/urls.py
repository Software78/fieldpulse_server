"""
URLs for sync app.
"""
from django.urls import path
from .views import BatchSyncView

app_name = 'sync'

urlpatterns = [
    path('batch/', BatchSyncView.as_view(), name='batch_sync'),
]
