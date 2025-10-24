# ===============================================
# performance/admin.py (Final Verified Version)
# ===============================================
# Django Admin configuration for Performance Evaluation module
# ===============================================

from django.contrib import admin
from .models import PerformanceEvaluation


@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing and managing employee performance evaluations.
    Provides search, filtering, and read-only scoring fields.
    """

    # Fields displayed in the list view
    list_display = (
        "get_emp_id",
        "get_employee_name",
        "department",
        "evaluation_type",
        "average_score",
        "total_score",
        "week_number",
        "year",
        "review_date",
    )

    # Filters for quick navigation
    list_filter = (
        "evaluation_type",
        "department",
        "year",
        "week_number",
    )

    # Searchable fields
    search_fields = (
        "employee__user__emp_id",
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__email",
        "department__name",
        "evaluation_type",
    )

    # Default ordering
    ordering = ("-review_date", "-created_at")

    # Read-only system fields
    readonly_fields = ("total_score", "average_score", "created_at", "updated_at")

    # -------------------------------------------------
    # Custom display methods
    # -------------------------------------------------
    def get_emp_id(self, obj):
        """Display Employee ID (from linked User)."""
        if obj.employee and obj.employee.user:
            return getattr(obj.employee.user, "emp_id", "-")
        return "-"
    get_emp_id.short_description = "Employee ID"

    def get_employee_name(self, obj):
        """Display Employee full name."""
        if obj.employee and obj.employee.user:
            first = obj.employee.user.first_name or ""
            last = obj.employee.user.last_name or ""
            full_name = f"{first} {last}".strip()
            return full_name or obj.employee.user.username
        return "-"
    get_employee_name.short_description = "Employee Name"
