# ===============================================
# performance/apps.py
# ===============================================
from django.apps import AppConfig

class PerformanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performance'
    verbose_name = 'Performance Evaluations'

    def ready(self):
        """
        Import signal handlers or scheduled tasks here safely.
        Avoid direct model imports at the top level!
        """
        try:
            import performance.signals 
        except ImportError:
            pass
