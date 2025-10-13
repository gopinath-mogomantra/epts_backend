from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Role


# -------------------------------------------------------------------
# 1️⃣ ROLE ADMIN CONFIGURATION
# -------------------------------------------------------------------
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'description', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    ordering = ('name',)
    list_per_page = 25


# -------------------------------------------------------------------
# 2️⃣ CUSTOM USER ADMIN CONFIGURATION
# -------------------------------------------------------------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Fields shown in the user list page
    list_display = (
        'id', 'username', 'emp_id', 'first_name', 'last_name',
        'email', 'role', 'is_active', 'is_verified', 'is_staff', 'joining_date'
    )

    # Filters on the right-hand side
    list_filter = ('role', 'is_active', 'is_verified', 'is_staff', 'is_superuser', 'joining_date')

    # Fields searchable by admin
    search_fields = ('username', 'emp_id', 'email', 'first_name', 'last_name')

    # Order by employee ID
    ordering = ('emp_id',)

    # For pagination performance
    list_per_page = 25

    # Group fields in the user detail/edit view
    fieldsets = (
        ('Basic Info', {
            'fields': ('username', 'emp_id', 'password')
        }),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'joining_date')
        }),
        ('Role & Status', {
            'fields': ('role', 'is_active', 'is_verified', 'is_staff', 'is_superuser')
        }),
        ('Permissions', {
            'fields': ('groups', 'user_permissions')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    # Fields for add-user form (when creating a new user)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'emp_id', 'email', 'password1', 'password2', 'role', 'is_active'),
        }),
    )
