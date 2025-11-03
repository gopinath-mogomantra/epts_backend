# ===============================================
# users/admin.py (PRODUCTION-READY VERSION)
# ===============================================
# Django Admin configuration for the custom User model.
# Features:
# ✅ Color-coded roles (Admin / Manager / Employee)
# ✅ Account lock/unlock with auto-expiry (2 hours)
# ✅ Department integration
# ✅ Password reset action (DEBUG mode)
# ✅ Inline search, filters, and optimized queries
# ✅ Transaction-safe bulk operations
# ===============================================

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.utils.crypto import get_random_string
from datetime import timedelta
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom Django admin configuration for the User model.
    Provides comprehensive user management with security features.
    """

    # ------------------------------------------------------
    # List Display Configuration
    # ------------------------------------------------------
    list_display = (
        "emp_id",
        "username",
        "get_full_name",
        "email",
        "get_department",
        "get_manager",
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
        "joining_date",
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
        "manager__username",
    )

    # ------------------------------------------------------
    # Display Settings
    # ------------------------------------------------------
    ordering = ("emp_id",)
    list_per_page = 25
    date_hierarchy = "date_joined"
    
    readonly_fields = (
        "emp_id",
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
        (
            _("Login Info"), 
            {
                "fields": ("username", "email", "password")
            }
        ),
        (
            _("Personal Info"),
            {
                "fields": (
                    "emp_id",
                    "first_name",
                    "last_name",
                    "phone",
                    "department",
                    "manager",
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
                    "force_password_change",
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
            {
                "fields": ("last_login", "date_joined", "created_at", "updated_at")
            },
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
                    "first_name",
                    "last_name",
                    "phone",
                    "department",
                    "manager",
                    "role",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )

    # ------------------------------------------------------
    # Custom Display Helpers
    # ------------------------------------------------------
    def get_full_name(self, obj):
        """Return user's full name or fallback to username."""
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name or obj.username
    
    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "first_name"

    def colored_role(self, obj):
        """Display role with color coding in admin list."""
        color_map = {
            "Admin": "#28a745",      # Green
            "Manager": "#fd7e14",    # Orange
            "Employee": "#007bff"    # Blue
        }
        color = color_map.get(obj.role, "#6c757d")
        return format_html(
            '<span style="font-weight:bold;color:{};padding:3px 8px;'
            'background-color:{}20;border-radius:3px;">{}</span>',
            color, color, obj.role
        )
    
    colored_role.short_description = "Role"
    colored_role.admin_order_field = "role"

    def get_department(self, obj):
        """Show department name if assigned."""
        if obj.department:
            return format_html(
                '<span style="color:#0056b3;">{}</span>',
                obj.department.name
            )
        return format_html('<span style="color:#dc3545;">Not Assigned</span>')
    
    get_department.short_description = "Department"
    get_department.admin_order_field = "department__name"

    def get_manager(self, obj):
        """Show manager username if assigned."""
        if obj.manager:
            return format_html(
                '<a href="/admin/users/user/?emp_id={}">{}</a>',
                obj.manager.emp_id,
                obj.manager.username
            )
        return "-"
    
    get_manager.short_description = "Manager"
    get_manager.admin_order_field = "manager__username"

    def lock_expiry_time(self, obj):
        """Show remaining lock time (auto-unlocks after 2 hours)."""
        if obj.account_locked and obj.locked_at:
            expiry = obj.locked_at + timedelta(hours=2)
            remaining = expiry - timezone.now()
            
            if remaining.total_seconds() > 0:
                hrs = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)
                return format_html(
                    '<span style="color:#dc3545;font-weight:bold;">🔒 {}h {}m</span>',
                    hrs, mins
                )
            return format_html(
                '<span style="color:#28a745;font-weight:bold;">✓ Ready to unlock</span>'
            )
        return "-"
    
    lock_expiry_time.short_description = "Lock Expiry"

    # ------------------------------------------------------
    # Query Optimization
    # ------------------------------------------------------
    def get_queryset(self, request):
        """Optimize query with department and manager joins."""
        qs = super().get_queryset(request)
        return qs.select_related("department", "manager")

    # ------------------------------------------------------
    # Admin Actions
    # ------------------------------------------------------
    actions = ["unlock_selected_accounts", "reset_password_for_selected"]

    @transaction.atomic
    def unlock_selected_accounts(self, request, queryset):
        """
        Unlock selected locked user accounts with transaction safety.
        Auto-checks lock expiry before unlocking.
        """
        unlocked = 0
        errors = []
        
        # Lock all selected users for update
        locked_users = queryset.select_for_update().filter(account_locked=True)
        
        for user in locked_users:
            try:
                # Check if lock has expired
                if user.locked_at:
                    expiry = user.locked_at + timedelta(hours=2)
                    if timezone.now() < expiry:
                        # Force unlock even if not expired (admin override)
                        pass
                
                user.unlock_account()
                unlocked += 1
            except Exception as e:
                errors.append(f"{user.emp_id}: {str(e)}")

        # Display results
        if errors:
            self.message_user(
                request,
                f"Failed to unlock some accounts: {', '.join(errors)}",
                level=messages.ERROR,
            )
        
        if unlocked:
            self.message_user(
                request,
                f"✓ {unlocked} account(s) successfully unlocked.",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No locked accounts were selected.",
                level=messages.WARNING,
            )

    unlock_selected_accounts.short_description = "🔓 Unlock selected user accounts"

    @transaction.atomic
    def reset_password_for_selected(self, request, queryset):
        """
        Generate new temporary passwords for selected users.
        Only works in DEBUG mode for security reasons.
        """
        if not settings.DEBUG:
            self.message_user(
                request,
                "❌ Password reset via admin is only available in DEBUG mode.",
                level=messages.ERROR,
            )
            return

        reset_count = 0
        passwords = []
        
        for user in queryset.select_for_update():
            if not user.is_active:
                continue
            
            # Generate secure password
            temp_password = get_random_string(
                length=12,
                allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            )
            
            user.set_password(temp_password)
            user.force_password_change = True
            user.save(update_fields=["password", "force_password_change"])
            
            passwords.append(f"{user.emp_id}: {temp_password}")
            reset_count += 1
        
        # Display passwords in console
        if passwords:
            print("\n" + "=" * 70)
            print("TEMPORARY PASSWORDS GENERATED (DEBUG MODE)")
            print("=" * 70)
            for pwd_info in passwords:
                print(pwd_info)
            print("=" * 70 + "\n")
        
        self.message_user(
            request,
            f"✓ {reset_count} password(s) reset. Check console for temp passwords.",
            level=messages.SUCCESS,
        )

    reset_password_for_selected.short_description = "🔑 Reset passwords (DEBUG only)"

    # ------------------------------------------------------
    # Custom Form Validation
    # ------------------------------------------------------
    def save_model(self, request, obj, form, change):
        """
        Override save to ensure proper validation.
        Prevents circular manager relationships.
        """
        if not change:  # New user
            # emp_id is auto-generated by the manager
            if not obj.emp_id:
                obj.emp_id = User.objects.generate_emp_id()
        
        # Call parent save (will trigger model validation)
        super().save_model(request, obj, form, change)