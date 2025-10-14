# ===============================================
# users/admin.py
# ===============================================
# Admin configuration for the custom User model.
# Supports: search, filtering, role management,
# and full CRUD via Django Admin.
# ===============================================

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for the User model.
    """

    # ✅ Fields visible in the list page
    list_display = (
        "id",
        "email",
        "emp_id",
        "first_name",
        "last_name",
        "role",
        "department",
        "is_active",
        "is_verified",
        "is_staff",
        "joining_date",
    )

    # ✅ Filters on right sidebar
    list_filter = (
        "role",
        "department",
        "is_active",
        "is_verified",
        "is_staff",
        "is_superuser",
    )

    # ✅ Searchable fields
    search_fields = ("email", "emp_id", "first_name", "last_name", "role")

    # ✅ Default ordering
    ordering = ("emp_id",)

    # ✅ Pagination for performance
    list_per_page = 25

    # ✅ Field grouping for edit form
    fieldsets = (
        (_("Login Info"), {"fields": ("email", "password")}),
        (_("Personal Info"), {
            "fields": (
                "emp_id",
                "first_name",
                "last_name",
                "phone",
                "department",
                "joining_date",
            )
        }),
        (_("Role & Access"), {
            "fields": (
                "role",
                "is_verified",
                "is_active",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        (_("Important Dates"), {"fields": ("last_login", "date_joined")}),
    )

    # ✅ Add-user form (Create user from Admin)
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "emp_id",
                    "first_name",
                    "last_name",
                    "role",
                    "department",
                    "password1",
                    "password2",
                    "is_active",
                ),
            },
        ),
    )
