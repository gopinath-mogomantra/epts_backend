# ===============================================
# employee/apps.py (Final Version)
# ===============================================

from django.apps import AppConfig


class EmployeeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "employee"
    verbose_name = "Employee Management"
