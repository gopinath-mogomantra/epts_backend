# ===============================================
# reports/admin.py (Final Verified Version)
# ===============================================
# Django Admin configuration for Cached Reports.
# Displays report type, period, and generation metadata.
# ===============================================

from django.contrib import admin
from .models import CachedReport


@admin.register(CachedReport)
class CachedReportAdmin(admin.ModelAdmin):
    """Admin configuration for Cached Report model."""

    # Columns displayed in list view
    list_display = (
        "id",
        "report_type",
        "get_period_display",
        "year",
        "week_number",
        "month",
        "manager",
        "department",
        "generated_by",
        "is_active",
        "generated_at",
    )

    # Filters and search
    list_filter = ("report_type", "year", "is_active")
    search_fields = (
        "report_type",
        "department__name",
        "manager__first_name",
        "manager__last_name",
        "generated_by__username",
    )
    ordering = ("-generated_at",)

    # Make certain fields read-only
    readonly_fields = ("generated_at", "file_path")

    # ---------------------------------------------
    # Helper display method
    # ---------------------------------------------
    def get_period_display(self, obj):
        """Display formatted period (Week/Month)."""
        return obj.get_period_display()
    get_period_display.short_description = "Period"
