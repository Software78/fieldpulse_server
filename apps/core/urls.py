"""
URL configuration for core app.
"""
from django.urls import path
from .views import HealthCheckView, simple_health_check

app_name = 'core'

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health_check'),
    path('health/simple/', simple_health_check, name='simple_health_check'),
]
