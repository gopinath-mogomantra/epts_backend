# ===============================================
# performance/admin.py
# ===============================================
# Admin registration for Performance Evaluation module.
# Supports filtering, search, and inline metric management.
# ===============================================

from django.contrib import admin
from django.utils.html import format_html
from .models import PerformanceEvaluation


@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    """
    Admin configuration for Performance Evaluation records.
    Provides analytics and easy access to employee evaluations.
    """

    # ------------------------------------------------------
    # Fields displayed in list view
    # ------------------------------------------------------
    list_display = (
        "id",
        "get_emp_id",
        "get_employee_name",
        "department",
        "evaluation_type",
        "review_date",
        "evaluation_period",
        "colored_total_score",
        "average_score",
        "evaluator",
    )

    # ------------------------------------------------------
    # Filters (right sidebar)
    # ------------------------------------------------------
    list_filter = (
        "evaluation_type",
        "department",
        "year",
        "week_number",
        "review_date",
    )

    # ------------------------------------------------------
    # Search bar
    # ------------------------------------------------------
    search_fields = (
        "employee__user__emp_id",
        "employee__user__first_name",
        "employee__user__last_name",
        "department__name",
        "evaluation_type",
    )

    # ------------------------------------------------------
    # Read-only fields
    # ------------------------------------------------------
    readonly_fields = (
        "total_score",
        "average_score",
        "created_at",
        "updated_at",
    )

    # ------------------------------------------------------
    # Default ordering and pagination
    # ------------------------------------------------------
    ordering = ("-review_date",)
    list_per_page = 25
    date_hierarchy = "review_date"

    # ------------------------------------------------------
    # Fieldsets (grouping sections in detail page)
    # ------------------------------------------------------
    fieldsets = (
        (
            "Employee & Review Info",
            {
                "fields": (
                    "employee",
                    "evaluator",
                    "department",
                    "evaluation_type",
                    "review_date",
                    "evaluation_period",
                    "week_number",
                    "year",
                )
            },
        ),
        (
            "Performance Metrics",
            {
                "fields": (
                    "communication_skills",
                    "multitasking",
                    "team_skills",
                    "technical_skills",
                    "job_knowledge",
                    "productivity",
                    "creativity",
                    "work_quality",
                    "professionalism",
                    "work_consistency",
                    "attitude",
                    "cooperation",
                    "dependability",
                    "attendance",
                    "punctuality",
                )
            },
        ),
        (
            "Summary",
            {
                "fields": (
                    "total_score",
                    "average_score",
                    "remarks",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    # ------------------------------------------------------
    # Custom column methods
    # ------------------------------------------------------
    def get_emp_id(self, obj):
        """Display employee ID in list view."""
        try:
            return obj.employee.user.emp_id
        except AttributeError:
            return "—"
    get_emp_id.short_description = "Emp ID"

    def get_employee_name(self, obj):
        """Display employee full name."""
        try:
            user = obj.employee.user
            return f"{user.first_name} {user.last_name}".strip() or "—"
        except AttributeError:
            return "—"
    get_employee_name.short_description = "Employee Name"

    def colored_total_score(self, obj):
        """Color-code total score for visual clarity."""
        color = "green"
        if obj.average_score < 50:
            color = "red"
        elif 50 <= obj.average_score < 75:
            color = "orange"
        return format_html(f"<b><span style='color:{color}'>{obj.total_score}</span></b>")
    colored_total_score.short_description = "Total Score"

    # ------------------------------------------------------
    # Save logic (ensures total_score auto recalculates)
    # ------------------------------------------------------
    def save_model(self, request, obj, form, change):
        obj.save()  # model.save() auto-updates total_score & average_score
        super().save_model(request, obj, form, change)

    # ------------------------------------------------------
    # Optimization: reduce DB hits in list view
    # ------------------------------------------------------
    def get_queryset(self, request):
        """Use select_related to optimize employee/department lookups."""
        qs = super().get_queryset(request)
        return qs.select_related("employee__user", "department", "evaluator")
