# ===============================================
# users/apps.py (Final Verified Version)
# ===============================================
# App configuration for the Users module.
# Handles initialization and admin labeling.
# ===============================================

from django.apps import AppConfig


class UsersConfig(AppConfig):
    """AppConfig for the Users module."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"
    verbose_name = "User Management"
