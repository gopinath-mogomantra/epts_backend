# ===========================================================
# employee/apps.py
# ===========================================================
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class EmployeeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "employee"
    verbose_name = "Employee Management"

    def ready(self):
        try:
            import employee.signals  # noqa: F401
            logger.info("✅ employee.signals successfully loaded.")
        except Exception as e:
            logger.error(f"⚠️ Failed to load employee.signals: {e}")
