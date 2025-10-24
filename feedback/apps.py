# ===============================================
# feedback/apps.py (Final Verified Version)
# ===============================================
# Defines the configuration for the 'feedback' app.
# Loaded automatically when included in INSTALLED_APPS.
# ===============================================

from django.apps import AppConfig


class FeedbackConfig(AppConfig):
    """AppConfig for the Feedback module (General, Manager, and Client Feedback)."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "feedback"
    verbose_name = "Employee Feedback Management"
