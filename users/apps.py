from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class UsersConfig(AppConfig):
    """
    Django application configuration for the Users app.

    - Registers model signals (e.g., auto-create Employee profile)
    - Uses lazy import to prevent circular imports
    - Adds verbose name for Django Admin display
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    verbose_name = "User Management"

    def ready(self):
        """
        Load signal handlers once Django is fully ready.
        This ensures signals like auto-employee creation
        are always connected, even during admin or migration.
        """
        try:
            import users.signals  # noqa: F401
            logger.info("✅ users.signals successfully loaded.")
        except Exception as e:
            logger.error(f"⚠️ Failed to load users.signals: {e}")
