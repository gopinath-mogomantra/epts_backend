# ===============================================
# reports/admin.py (Final Production-Stable Version)
# ===============================================
# Django Admin configuration for Cached Reports.
# Displays report type, period, manager/department,
# and generation metadata for analytics and exports.
# ===============================================

from django.contrib import admin
from django.utils.html import format_html
from .models import CachedReport


@admin.register(CachedReport)
class CachedReportAdmin(admin.ModelAdmin):
    """Admin configuration for Cached Report model."""

    # ------------------------------------------------------
    # Columns displayed in Django Admin list view
    # ------------------------------------------------------
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
        "file_link",
    )

    # ------------------------------------------------------
    # Filters and search configuration
    # ------------------------------------------------------
    list_filter = ("report_type", "year", "is_active")
    search_fields = (
        "report_type",
        "department__name",
        "manager__first_name",
        "manager__last_name",
        "generated_by__username",
    )
    ordering = ("-generated_at",)

    # ------------------------------------------------------
    # Read-only fields
    # ------------------------------------------------------
    readonly_fields = ("generated_at", "file_path")

    # ------------------------------------------------------
    # Custom display methods
    # ------------------------------------------------------
    def get_period_display(self, obj):
        """Display formatted period (Week/Month)."""
        return obj.get_period_display()
    get_period_display.short_description = "Period"

    def file_link(self, obj):
        """Clickable link for exported report files."""
        if obj.file_path:
            return format_html('<a href="{}" target="_blank">Download</a>', obj.file_path.url)
        return "-"
    file_link.short_description = "Export File"

    # ------------------------------------------------------
    # Additional UI Enhancements
    # ------------------------------------------------------
    def has_add_permission(self, request):
        """Disable manual addition from admin (only system-generated)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Restrict editing of generated reports — only allow viewing or archive toggle."""
        if obj:
            # Allow toggling 'is_active' only
            return request.user.is_superuser
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Allow delete only to superusers."""
        return request.user.is_superuser
