# ===============================================
# users/admin.py
# ===============================================
# Admin configuration for the custom User model.
# Supports: search, filtering, role management,
# inline department linkage, and full CRUD.
# ===============================================

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for the User model (username-based login).
    Integrated with department info and color-coded roles.
    """

    # ------------------------------------------------------
    # ✅ Fields visible in list view
    # ------------------------------------------------------
    list_display = (
        "emp_id",
        "username",
        "get_full_name",
        "email",
        "get_department",
        "colored_role",
        "is_active",
        "is_verified",
        "is_staff",
        "joining_date",
    )

    # ------------------------------------------------------
    # ✅ Filters (right sidebar)
    # ------------------------------------------------------
    list_filter = (
        "role",
        "department",
        "is_active",
        "is_verified",
        "is_staff",
        "is_superuser",
    )

    # ------------------------------------------------------
    # ✅ Searchable fields
    # ------------------------------------------------------
    search_fields = (
        "emp_id",
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "department__name",
    )

    # ------------------------------------------------------
    # ✅ Ordering, pagination, and readonly fields
    # ------------------------------------------------------
    ordering = ("emp_id",)
    list_per_page = 25
    readonly_fields = ("created_at", "updated_at", "date_joined", "last_login")

    # ------------------------------------------------------
    # ✅ Fieldsets for detail/edit page
    # ------------------------------------------------------
    fieldsets = (
        (_("Login Info"), {"fields": ("username", "email", "password")}),
        (
            _("Personal Info"),
            {
                "fields": (
                    "emp_id",
                    "first_name",
                    "last_name",
                    "phone",
                    "department",
                    "joining_date",
                )
            },
        ),
        (
            _("Role & Access"),
            {
                "fields": (
                    "role",
                    "is_verified",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("System Info"),
            {"fields": ("last_login", "date_joined", "created_at", "updated_at")},
        ),
    )

    # ------------------------------------------------------
    # ✅ Fields shown when adding a new user from Admin
    # ------------------------------------------------------
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "emp_id",
                    "first_name",
                    "last_name",
                    "phone",
                    "department",
                    "role",
                    "password",
                    "is_active",
                ),
            },
        ),
    )

    # ------------------------------------------------------
    # ✅ Custom display methods
    # ------------------------------------------------------
    def get_full_name(self, obj):
        """Display the full name of the user (fallback to username)."""
        full_name = f"{obj.first_name} {obj.last_name}".strip() or obj.username
        return full_name
    get_full_name.short_description = "Full Name"

    def colored_role(self, obj):
        """Show role with color-coded style."""
        color_map = {
            "Admin": "green",
            "Manager": "orange",
            "Employee": "blue",
        }
        color = color_map.get(obj.role, "black")
        return format_html(f"<b><span style='color:{color}'>{obj.role}</span></b>")
    colored_role.short_description = "Role"

    def get_department(self, obj):
        """Display department name safely."""
        return obj.department.name if obj.department else "-"
    get_department.short_description = "Department"

    # ------------------------------------------------------
    # ✅ Query optimization
    # ------------------------------------------------------
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("department")
