# ===============================================
# employee/admin.py
# ===============================================
# Django Admin configuration for Employee & Department
# Linked with the custom User model
# ===============================================

from django.contrib import admin
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
        (None, {"fields": ("name", "description", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


# =====================================================
# ✅ Employee Admin
# =====================================================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Manage employee profiles in Django Admin.
    Shows linked User info (emp_id, name, email, role).
    """
    # Columns visible in list view
    list_display = (
        "get_emp_id",
        "get_full_name",
        "get_email",
        "get_role",
        "department",
        "designation",
        "manager_name",
        "status",
        "date_joined",
    )

    # Filters on right-side panel
    list_filter = ("status", "department", "date_joined")

    # Search bar
    search_fields = (
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

    # ------------------------------
    # ✅ Custom display methods
    # ------------------------------
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()
    get_full_name.short_description = "Employee Name"

    def get_emp_id(self, obj):
        return obj.user.emp_id
    get_emp_id.short_description = "Emp ID"

    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = "Email"

    def get_role(self, obj):
        return obj.user.role
    get_role.short_description = "Role"

    # ✅ Optimize queryset (reduce DB hits)
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "department", "manager")
