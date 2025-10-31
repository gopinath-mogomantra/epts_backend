# ===============================================
# users/admin.py
# ===============================================
# Django Admin configuration for the custom User model.
# Features:
# ✅ Color-coded roles (Admin / Manager / Employee)
# ✅ Account lock/unlock with auto-expiry (2 hours)
# ✅ Department integration
# ✅ Inline search, filters, and optimized queries
# ===============================================

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom Django admin configuration for the User model."""

    # ------------------------------------------------------
    # List Display Configuration
    # ------------------------------------------------------
    list_display = (
        "emp_id",
        "username",
        "get_full_name",
        "email",
        "get_department",
        "colored_role",
        "is_active",
        "account_locked",
        "failed_login_attempts",
        "lock_expiry_time",
        "is_verified",
        "is_staff",
        "joining_date",
    )

    # ------------------------------------------------------
    # Filters (Sidebar)
    # ------------------------------------------------------
    list_filter = (
        "role",
        "department",
        "is_active",
        "account_locked",
        "is_verified",
        "is_staff",
        "is_superuser",
    )

    # ------------------------------------------------------
    # Searchable Fields
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
    # Display Settings
    # ------------------------------------------------------
    ordering = ("emp_id",)
    list_per_page = 25
    readonly_fields = (
        "created_at",
        "updated_at",
        "date_joined",
        "last_login",
        "failed_login_attempts",
        "account_locked",
        "locked_at",
    )

    # ------------------------------------------------------
    # Fieldsets (Detail Page Layout)
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
            _("Security Status"),
            {
                "fields": (
                    "failed_login_attempts",
                    "account_locked",
                    "locked_at",
                ),
                "description": "Tracks login attempts, lock status, and lock timestamps.",
            },
        ),
        (
            _("System Info"),
            {"fields": ("last_login", "date_joined", "created_at", "updated_at")},
        ),
    )

    # ------------------------------------------------------
    # Add User Page Configuration
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
    # Custom Display Helpers
    # ------------------------------------------------------
    def get_full_name(self, obj):
        """Return user's full name or fallback to username."""
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username
    get_full_name.short_description = "Full Name"

    def colored_role(self, obj):
        """Display role with color coding in admin list."""
        color_map = {"Admin": "green", "Manager": "orange", "Employee": "blue"}
        color = color_map.get(obj.role, "black")
        return format_html(f"<b><span style='color:{color}'>{obj.role}</span></b>")
    colored_role.short_description = "Role"

    def get_department(self, obj):
        """Show department name if assigned."""
        return obj.department.name if obj.department else "-"
    get_department.short_description = "Department"

    def lock_expiry_time(self, obj):
        """Show remaining lock time (auto-unlocks after 2 hours)."""
        if obj.account_locked and obj.locked_at:
            expiry = obj.locked_at + timedelta(hours=2)
            remaining = expiry - timezone.now()
            if remaining.total_seconds() > 0:
                hrs = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                return format_html(
                    f"<span style='color:red;'>Unlocks in {hrs}h {mins}m</span>"
                )
            return format_html("<span style='color:green;'>Ready to unlock</span>")
        return "-"
    lock_expiry_time.short_description = "Lock Expiry"

    # ------------------------------------------------------
    # Query Optimization
    # ------------------------------------------------------
    def get_queryset(self, request):
        """Optimize query with department joins."""
        qs = super().get_queryset(request)
        return qs.select_related("department")

    # ------------------------------------------------------
    # Admin Actions
    # ------------------------------------------------------
    actions = ["unlock_selected_accounts"]

    def unlock_selected_accounts(self, request, queryset):
        """Unlock selected locked user accounts."""
        unlocked = 0
        for user in queryset:
            if user.account_locked:
                user.unlock_account()
                unlocked += 1

        if unlocked:
            self.message_user(
                request,
                f"{unlocked} account(s) successfully unlocked.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No locked accounts were selected.",
                level=messages.WARNING,
            )

    unlock_selected_accounts.short_description = "Unlock selected user accounts"
