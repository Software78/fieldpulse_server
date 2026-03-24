"""
URLs for media app.
"""
from django.urls import path
from . import views

app_name = 'media_app'

urlpatterns = [
    path('photos/', views.photo_upload_view, name='photo_upload'),
    path('photos/<uuid:photo_id>/', views.photo_proxy_view, name='photo_proxy'),
    path('signatures/', views.signature_upload_view, name='signature_upload'),
    path('signatures/<uuid:signature_id>/', views.signature_proxy_view, name='signature_proxy'),
]
