# ===============================================
# performance/admin.py
# ===============================================
# Django Admin configuration for the Performance Evaluation module.
# Features:
# ✅ Displays weekly performance with scoring breakdown
# ✅ Rank indicator for top performers
# ✅ Department, week, and year filtering
# ✅ Search by employee name, ID, or department
# ===============================================

from django.contrib import admin
from django.utils.html import format_html
from .models import PerformanceEvaluation


@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    """
    Admin interface for viewing and managing employee performance evaluations.
    Provides advanced filtering, search, and read-only scoring fields.
    """

    # -------------------------------------------------
    # List Display Configuration
    # -------------------------------------------------
    list_display = (
        "get_emp_id",
        "get_employee_name",
        "department",
        "evaluation_type",
        "colored_score",
        "total_score",
        "rank_icon",
        "week_number",
        "year",
        "review_date",
    )

    # -------------------------------------------------
    # Filters (Sidebar)
    # -------------------------------------------------
    list_filter = (
        "evaluation_type",
        "department",
        "year",
        "week_number",
    )

    # -------------------------------------------------
    # Searchable Fields
    # -------------------------------------------------
    search_fields = (
        "employee__user__emp_id",
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__email",
        "department__name",
        "evaluation_type",
    )

    # -------------------------------------------------
    # Display Settings
    # -------------------------------------------------
    ordering = ("-year", "-week_number", "-average_score")
    list_per_page = 25
    readonly_fields = ("total_score", "average_score", "created_at", "updated_at")

    # -------------------------------------------------
    # Custom Display Methods
    # -------------------------------------------------
    def get_emp_id(self, obj):
        """Display Employee ID (from linked User)."""
        if obj.employee and obj.employee.user:
            return getattr(obj.employee.user, "emp_id", "-")
        return "-"
    get_emp_id.short_description = "Employee ID"

    def get_employee_name(self, obj):
        """Display full name of the employee."""
        if obj.employee and obj.employee.user:
            first = obj.employee.user.first_name or ""
            last = obj.employee.user.last_name or ""
            return f"{first} {last}".strip() or obj.employee.user.username
        return "-"
    get_employee_name.short_description = "Employee Name"

    def colored_score(self, obj):
        """Display average score with color coding."""
        score = obj.average_score or 0
        if score >= 85:
            color = "green"
        elif score >= 70:
            color = "orange"
        else:
            color = "red"
        return format_html(f"<b><span style='color:{color};'>{score}%</span></b>")
    colored_score.short_description = "Average Score"

    def rank_icon(self, obj):
        """Display medal emoji for top performers."""
        if obj.rank and obj.rank <= 3:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            return format_html(f"<b>{medals.get(obj.rank, '')} #{obj.rank}</b>")
        elif obj.rank:
            return f"#{obj.rank}"
        return "-"
    rank_icon.short_description = "Rank"
