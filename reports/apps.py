# ===============================================
# reports/apps.py 
# ===============================================
# App configuration for the Reports module.
# Handles registration and initialization.
# ===============================================

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    """AppConfig for the Reports module."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "reports"
    verbose_name = "Reports & Analytics"
