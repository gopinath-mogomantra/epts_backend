# ===============================================
# performance/admin.py
# ===============================================
# Django Admin configuration for Performance Evaluation module
# ===============================================

from django.contrib import admin
from .models import PerformanceEvaluation


@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing and managing employee performance evaluations.
    Provides search, filtering, and read-only scoring.
    """

    # Fields displayed in the list view
    list_display = (
        "id",
        "get_emp_id",
        "get_employee_name",
        "department",
        "evaluation_type",
        "average_score",
        "total_score",
        "week_number",
        "year",
        "review_date",
        "created_at",
    )

    # Filters for sidebar filtering
    list_filter = (
        "evaluation_type",
        "department",
        "year",
        "week_number",
    )

    # Fields that can be searched in admin
    search_fields = (
        "employee__user__emp_id",
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__email",
        "department__name",
        "evaluation_type",
    )

    # Default ordering (most recent first)
    ordering = ("-review_date", "-created_at")

    # Make computed fields read-only
    readonly_fields = ("total_score", "average_score", "created_at", "updated_at")

    # Custom display methods
    def get_emp_id(self, obj):
        """Fetch Employee ID from linked user."""
        return getattr(obj.employee.user, "emp_id", "-") if obj.employee and obj.employee.user else "-"
    get_emp_id.short_description = "Emp ID"

    def get_employee_name(self, obj):
        """Return the employee's full name."""
        if obj.employee and obj.employee.user:
            full_name = f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip()
            return full_name or obj.employee.user.username
        return "Unknown"
    get_employee_name.short_description = "Employee Name"
