# ===============================================
# employee/admin.py (Final Verified — Admin & Frontend Ready)
# ===============================================
# Django Admin configuration for Employee and Department models.
# Features:
# ✅ Department management with active/inactive toggle
# ✅ Employee admin with linked user data (name, email, emp_id, role)
# ✅ Inline search, filtering, and role-aware display
# ===============================================

from django.contrib import admin
from django.utils.html import format_html
from .models import Employee, Department


# =====================================================
# 🏢 DEPARTMENT ADMIN
# =====================================================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model."""

    list_display = (
        "id",
        "name",
        "description",
        "colored_status",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "description", "code")
    list_filter = ("is_active", "created_at")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")

    # --------------------------------------------
    # Helper Display Methods
    # --------------------------------------------
    def colored_status(self, obj):
        """Show green if active, red if inactive."""
        color = "green" if obj.is_active else "red"
        status = "Active" if obj.is_active else "Inactive"
        return format_html(f"<b><span style='color:{color};'>{status}</span></b>")
    colored_status.short_description = "Status"


# =====================================================
# 👨‍💼 EMPLOYEE ADMIN
# =====================================================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Admin configuration for Employee model.
    Displays linked user details and department information.
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

    # --------------------------------------------
    # Helper Display Methods
    # --------------------------------------------
    def get_full_name(self, obj):
        """Return the full name of the employee (from linked User)."""
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
