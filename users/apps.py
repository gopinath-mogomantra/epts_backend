# ===========================================================
# users/apps.py (Final — Signal-Ready & Production Verified)
# ===========================================================
# Handles:
# - App registration for User Management
# - Auto-loads signals for employee auto-creation
# - Adds structured logging for signal loading status
# ===========================================================

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class UsersConfig(AppConfig):
    """
    Django AppConfig for the Users module.

    Responsibilities:
    ----------------------------------------------------------
    • Registers user-related signals (e.g., auto-create Employee)
    • Prevents circular imports by lazy-loading inside ready()
    • Adds verbose name for Django Admin
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    verbose_name = "User Management"

    def ready(self):
        """
        ✅ Load signal handlers when Django starts.
        Ensures user-to-employee auto-creation logic is connected.
        """
        try:
            import users.signals  # noqa: F401
            logger.info("✅ [UsersConfig] users.signals successfully loaded.")
        except Exception as e:
            logger.exception(f"⚠️ [UsersConfig] Failed to load users.signals: {e}")
