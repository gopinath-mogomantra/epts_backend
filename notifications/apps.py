# ===============================================
# notifications/apps.py
# ===============================================
# App configuration for the Notifications module.
# Handles registration and automatic signal loading.
# ===============================================

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """AppConfig for the Notifications module."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"
    verbose_name = "User Notifications"

    def ready(self):
        """
        Import and register notification signals if defined.
        This ensures automatic trigger setup on startup.
        """
        try:
            import notifications.signals
        except Exception:
            pass
