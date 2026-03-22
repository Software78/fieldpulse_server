"""
Sync app configuration.
"""
from django.apps import AppConfig


class SyncConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sync'
    verbose_name = 'Sync'
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import apps.sync.signals
        except ImportError:
            pass
