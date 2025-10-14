# ===============================================
# employee/admin.py
# ===============================================
# Django Admin configuration for Employee & Department
# Linked with the custom User model.
# Includes color-coded status and manager linkage.
# ===============================================

from django.contrib import admin
from django.utils.html import format_html
from .models import Employee, Department


# =====================================================
# ✅ Department Admin
# =====================================================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """
    Manage company departments from Django Admin.
    """
    list_display = ("id", "name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    ordering = ("name",)
    list_per_page = 25
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Department Info", {"fields": ("name", "description", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def save_model(self, request, obj, form, change):
        """
        Ensures department name consistency (capitalize first letter).
        """
        obj.name = obj.name.strip().title()
        super().save_model(request, obj, form, change)


# =====================================================
# ✅ Employee Admin
# =====================================================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Manage employee profiles in Django Admin.
    Displays linked User info and supports search, filter, and inline management.
    """

    # Columns visible in list view
    list_display = (
        "get_emp_id",
        "get_full_name",
        "get_email",
        "get_role_colored",
        "department",
        "designation",
        "get_manager_name",
        "colored_status",
        "date_joined",
    )

    # Filters on right-side panel
    list_filter = ("status", "department", "user__role", "date_joined")

    # Search bar
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__emp_id",
        "user__email",
        "department__name",
    )

    ordering = ("user__emp_id",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25

    fieldsets = (
        ("Employee Details", {
            "fields": (
                "user",
                "department",
                "manager",
                "designation",
                "status",
                "date_joined",
            )
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    # ------------------------------------------------------
    # ✅ Custom display methods (linked from User)
    # ------------------------------------------------------
    def get_emp_id(self, obj):
        """Employee ID"""
        return obj.user.emp_id if obj.user else "-"
    get_emp_id.short_description = "Emp ID"

    def get_full_name(self, obj):
        """Employee Full Name"""
        if obj.user:
            name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            return name or obj.user.username
        return "-"
    get_full_name.short_description = "Employee Name"

    def get_email(self, obj):
        """Employee Email"""
        return obj.user.email if obj.user else "-"
    get_email.short_description = "Email"

    def get_manager_name(self, obj):
        """Manager Name"""
        if obj.manager and obj.manager.user:
            return f"{obj.manager.user.first_name} {obj.manager.user.last_name}".strip()
        return "-"
    get_manager_name.short_description = "Manager"

    def get_role_colored(self, obj):
        """Color-coded role display."""
        if not obj.user:
            return "-"
        color_map = {
            "Admin": "green",
            "Manager": "orange",
            "Employee": "blue",
        }
        color = color_map.get(obj.user.role, "black")
        return format_html(f"<b><span style='color:{color}'>{obj.user.role}</span></b>")
    get_role_colored.short_description = "Role"

    def colored_status(self, obj):
        """Color-coded status for quick visual reference."""
        color = {
            "Active": "green",
            "On Leave": "orange",
            "Resigned": "red",
        }.get(obj.status, "gray")
        return format_html(f"<b><span style='color:{color}'>{obj.status}</span></b>")
    colored_status.short_description = "Status"

    # ------------------------------------------------------
    # ✅ Query optimization (avoid N+1 queries)
    # ------------------------------------------------------
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("user", "department", "manager__user")
        )
