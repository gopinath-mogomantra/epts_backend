# ===============================================
# notifications/admin.py
# ===============================================
# Django Admin configuration for Notifications.
# Displays notification status, recipient, and timestamps.
# ===============================================

from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin configuration for the Notification model."""
    
    # Columns shown in admin list
    list_display = (
        "id",
        "get_emp_id",
        "get_employee_name",
        "message",
        "is_read",
        "auto_delete",
        "created_at",
        "read_at",
    )
    
    # Filters and search
    list_filter = ("is_read", "auto_delete", "created_at")
    search_fields = (
        "employee__email",
        "employee__first_name",
        "employee__last_name",
        "employee__emp_id",
        "message",
    )
    ordering = ("-created_at",)

    # ---------------------------------------------
    # Helper display methods
    # ---------------------------------------------
    def get_emp_id(self, obj):
        return getattr(obj.employee, "emp_id", "-")
    get_emp_id.short_description = "Emp ID"

    def get_employee_name(self, obj):
        """Return recipient's full name."""
        if obj.employee:
            first = getattr(obj.employee, "first_name", "")
            last = getattr(obj.employee, "last_name", "")
            return f"{first} {last}".strip() or obj.employee.username
        return "-"
    get_employee_name.short_description = "Employee Name"
