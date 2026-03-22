"""
Media app configuration.
"""
from django.apps import AppConfig


class MediaAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.media_app'
    verbose_name = 'Media'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.media_app.signals
        except ImportError:
            pass
