"""
URLs for media app.
"""
from django.urls import path
from . import views

app_name = 'media_app'

urlpatterns = [
    path('photos/', views.photo_upload_view, name='photo_upload'),
    path('signatures/', views.signature_upload_view, name='signature_upload'),
]
