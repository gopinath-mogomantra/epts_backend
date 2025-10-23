# ===============================================
# employee/admin.py
# ===============================================
# Django Admin configuration for Employee and Department models
# ===============================================

from django.contrib import admin
from .models import Employee, Department


# =====================================================
# DEPARTMENT ADMIN
# =====================================================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "is_active", "created_at")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    ordering = ("name",)


# =====================================================
# EMPLOYEE ADMIN
# =====================================================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Custom admin configuration for Employee model.
    Displays key employee info, supports searching and filtering.
    """

    # Display key fields in the Employee list page
    list_display = (
        "id",
        "emp_id",
        "get_full_name",
        "email",
        "department",
        "designation",
        "role",
        "status",
        "joining_date",
    )

    # Enable search on useful text fields
    search_fields = (
        "user__emp_id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "designation",
    )

    # Filters for quick navigation
    list_filter = ("department", "status", "joining_date")

    # Order employees alphabetically by user first name
    ordering = ("user__first_name",)

    # Make related user fields readable
    readonly_fields = ("created_at", "updated_at")

    # -------------------------------------------------
    # Helper display methods
    # -------------------------------------------------
    def get_full_name(self, obj):
        """Display the user's full name (from linked user)."""
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
        return "-"
    get_full_name.short_description = "Employee Name"

    def emp_id(self, obj):
        """Shortcut to linked user's employee ID."""
        return getattr(obj.user, "emp_id", "-")
    emp_id.short_description = "Employee ID"

    def email(self, obj):
        """Shortcut to linked user's email."""
        return getattr(obj.user, "email", "-")
    email.short_description = "Email"

    def role(self, obj):
        """Shortcut to linked user's role (if available)."""
        return getattr(obj.user, "role", "-")
    role.short_description = "Role"
