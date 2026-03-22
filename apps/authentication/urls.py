"""
URLs for authentication app.
"""
from django.urls import path
from .views import (
    LoginView,
    TokenRefreshViewCustom,
    LogoutView,
    MeView,
    FCMTokenView,
)

app_name = 'authentication'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshViewCustom.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path('fcm-token/', FCMTokenView.as_view(), name='fcm_token'),
]
