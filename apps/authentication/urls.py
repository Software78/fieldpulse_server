"""
URLs for authentication app.
"""
from django.urls import path
from .views import (
    LoginView,
    TokenRefreshViewCustom,
    MeView,
)

app_name = 'authentication'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshViewCustom.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
]
