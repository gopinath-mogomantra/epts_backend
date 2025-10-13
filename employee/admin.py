from django.contrib import admin
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Configuration for displaying Employee data in the Django Admin panel.
    Provides search, filter, and sorting functionality for convenience.
    """

    # 🔹 Columns visible in the admin list view
    list_display = (
        'get_emp_id',
        'get_full_name',
        'department',
        'manager_name',
        'status',
        'joining_date',
    )

    # 🔹 Filters (right-side panel in Django admin)
    list_filter = ('status', 'department', 'joining_date')

    # 🔹 Search bar functionality
    search_fields = (
        'user__first_name',
        'user__last_name',
        'user__emp_id',
        'department',
    )

    # 🔹 Default ordering of employee records
    ordering = ('user__emp_id',)

    # 🔹 Optional: read-only audit fields
    readonly_fields = ('created_at', 'updated_at')

    # 🔹 Display proper labels in admin
    def get_full_name(self, obj):
        """Returns employee's full name."""
        return f"{obj.user.first_name} {obj.user.last_name}".strip()
    get_full_name.short_description = 'Employee Name'

    def get_emp_id(self, obj):
        """Returns employee ID from related CustomUser."""
        return obj.user.emp_id
    get_emp_id.short_description = 'Emp ID'
