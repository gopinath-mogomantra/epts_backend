# ===============================================
# employee/admin.py (Final Verified — Admin & Frontend Ready)
# ===============================================
# Django Admin configuration for Employee and Department models.
# Features:
# ✅ Department management with real-time employee count
# ✅ Employee admin with linked user info (emp_id, email, role, dept)
# ✅ Inline search, filters, role badges, and status color coding
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
        "code",
        "employee_count",
        "colored_status",
        "created_at",
        "updated_at",
    )
    search_fields = ("name", "description", "code")
    list_filter = ("is_active", "created_at")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at", "employee_count")

    # --------------------------------------------
    # Helper Display Methods
    # --------------------------------------------
    def colored_status(self, obj):
        """Show green if active, red if inactive."""
        color = "green" if obj.is_active else "red"
        status = "Active" if obj.is_active else "Inactive"
        return format_html(f"<b><span style='color:{color};'>{status}</span></b>")

    colored_status.short_description = "Status"

    def get_queryset(self, request):
        """Prefetch employees for optimized display."""
        qs = super().get_queryset(request)
        return qs.prefetch_related("employees")


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
        "emp_id",
        "get_full_name",
        "get_email",
        "department",
        "designation",
        "colored_role",
        "status",
        "joining_date",
    )
    search_fields = (
        "emp_id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "designation",
    )
    list_filter = ("department", "role", "status", "joining_date")
    ordering = ("emp_id",)
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
    get_full_name.short_description = "Full Name"

    def get_email(self, obj):
        """Return linked user's email address."""
        return getattr(obj.user, "email", "-")
    get_email.short_description = "Email"

    def colored_role(self, obj):
        """Display role as colored badge for better visibility."""
        role_colors = {
            "Admin": "#007bff",
            "Manager": "#28a745",
            "Employee": "#6c757d",
        }
        color = role_colors.get(obj.role, "#999")
        return format_html(
            f"<span style='background-color:{color}; color:white; padding:3px 8px; border-radius:4px;'>{obj.role}</span>"
        )
    colored_role.short_description = "Role"

    # --------------------------------------------
    # Optimization Hooks
    # --------------------------------------------
    def get_queryset(self, request):
        """Optimize query performance for admin list view."""
        qs = super().get_queryset(request)
        return qs.select_related("user", "department", "manager")

    def save_model(self, request, obj, form, change):
        """Custom save logic with admin audit logging."""
        super().save_model(request, obj, form, change)
        if change:
            self.message_user(
                request,
                f"✅ Employee '{obj.emp_id}' details updated successfully.",
            )
        else:
            self.message_user(
                request,
                f"✅ Employee '{obj.emp_id}' added successfully.",
            )
