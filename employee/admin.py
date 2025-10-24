# ===============================================
# employee/admin.py (Final Verified Version)
# ===============================================
# Django Admin configuration for Employee and Department models
# ===============================================

from django.contrib import admin
from .models import Employee, Department


# =====================================================
# 🔹 DEPARTMENT ADMIN
# =====================================================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model."""
    list_display = ("id", "name", "description", "is_active", "created_at")
    search_fields = ("name", "description")
    list_filter = ("is_active",)
    ordering = ("name",)


# =====================================================
# 🔹 EMPLOYEE ADMIN
# =====================================================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Custom admin configuration for Employee model.
    Displays key employee info, supports searching and filtering.
    """

    list_display = (
        "get_emp_id",
        "get_full_name",
        "get_email",
        "department",
        "designation",
        "get_role",
        "status",
        "joining_date",
    )
    search_fields = (
        "user__emp_id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "designation",
    )
    list_filter = ("department", "status", "joining_date")
    ordering = ("user__first_name",)
    readonly_fields = ("created_at", "updated_at")

    # -------------------------------------------------
    # Helper display methods
    # -------------------------------------------------
    def get_full_name(self, obj):
        """Return the full name of the employee (from linked user)."""
        if obj.user:
            full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            return full_name or obj.user.username
        return "-"
    get_full_name.short_description = "Employee Name"

    def get_emp_id(self, obj):
        """Return linked user's employee ID."""
        return getattr(obj.user, "emp_id", "-")
    get_emp_id.short_description = "Employee ID"

    def get_email(self, obj):
        """Return linked user's email address."""
        return getattr(obj.user, "email", "-")
    get_email.short_description = "Email"

    def get_role(self, obj):
        """Return linked user's assigned role."""
        return getattr(obj.user, "role", "-")
    get_role.short_description = "Role"
