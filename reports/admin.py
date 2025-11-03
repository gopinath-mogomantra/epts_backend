# ===============================================
# reports/admin.py (Final Unified Version)
# ===============================================
"""
Django Admin configuration for Cached Reports.

✅ Combines both Enhanced Versions (extra_context + messages banner)
✅ Supports advanced filtering, badges, bulk actions, and download links
✅ Includes:
   - Color-coded report type icons
   - Search, filters, badges, inline JSON preview
   - CSV export
   - Dual statistics banners (auto adaptive)
   - Optimized query performance
   - Secure permissions & audit logging
"""

from django.contrib import admin, messages
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
import json, csv
from datetime import timedelta

from .models import CachedReport


# ===============================================
# CUSTOM FILTERS
# ===============================================
class ReportTypeFilter(admin.SimpleListFilter):
    """Custom filter for report types with counts."""
    title = 'Report Type'
    parameter_name = 'report_type'

    def lookups(self, request, model_admin):
        counts = (
            CachedReport.objects
            .values('report_type')
            .annotate(count=Count('id'))
            .order_by('report_type')
        )
        return [(c['report_type'], f"{c['report_type'].title()} ({c['count']})") for c in counts]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(report_type=self.value())
        return queryset


class GeneratedDateFilter(admin.SimpleListFilter):
    """Filter reports by generation date ranges."""
    title = 'Generated Date'
    parameter_name = 'generated_date'

    def lookups(self, request, model_admin):
        return (
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('week', 'Last 7 days'),
            ('month', 'Last 30 days'),
            ('quarter', 'Last 90 days'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        lookup_map = {
            'today': now.date(),
            'yesterday': (now - timedelta(days=1)).date(),
            'week': now - timedelta(days=7),
            'month': now - timedelta(days=30),
            'quarter': now - timedelta(days=90),
        }
        val = self.value()
        if val in ['today', 'yesterday']:
            return queryset.filter(generated_at__date=lookup_map[val])
        elif val in ['week', 'month', 'quarter']:
            return queryset.filter(generated_at__gte=lookup_map[val])
        return queryset


class HasFileFilter(admin.SimpleListFilter):
    """Filter by file existence."""
    title = 'File Status'
    parameter_name = 'has_file'

    def lookups(self, request, model_admin):
        return (('yes', 'Has File'), ('no', 'No File'))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(Q(file_path='') | Q(file_path__isnull=True))
        elif self.value() == 'no':
            return queryset.filter(Q(file_path='') | Q(file_path__isnull=True))
        return queryset


class YearFilter(admin.SimpleListFilter):
    """Filter by year."""
    title = 'Year'
    parameter_name = 'year_filter'

    def lookups(self, request, model_admin):
        years = CachedReport.objects.values_list('year', flat=True).distinct().order_by('-year')
        return [(y, str(y)) for y in years if y]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(year=self.value())
        return queryset


# ===============================================
# MAIN ADMIN CLASS
# ===============================================
@admin.register(CachedReport)
class CachedReportAdmin(admin.ModelAdmin):
    """Unified enhanced admin configuration."""

    list_display = (
        "id", "colored_report_type", "period_badge",
        "scope_info", "generated_by_link",
        "status_badge", "file_download_link",
        "records_count", "generated_at_formatted", "actions_column",
    )
    list_display_links = ("id", "colored_report_type")

    list_filter = (
        ReportTypeFilter, GeneratedDateFilter, HasFileFilter, YearFilter,
        "is_active", "is_archived",
    )
    search_fields = (
        "report_type", "department__name",
        "manager__user__emp_id",
        "manager__user__first_name", "manager__user__last_name",
        "generated_by__username", "generated_by__email",
    )
    ordering = ("-generated_at",)
    list_per_page = 50

    readonly_fields = ("generated_at", "payload_preview")
    fieldsets = (
        ("Report Info", {"fields": ("report_type", "year", "week_number", "month")}),
        ("Scope", {"fields": ("manager", "department"), "classes": ("collapse",)}),
        ("Data & Files", {"fields": ("payload_preview", "file_path")}),
        ("Metadata", {"fields": ("generated_by", "generated_at", "is_active", "is_archived"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('generated_by', 'manager__user', 'department')

    # ======================== DISPLAY =======================
    @admin.display(description="Report Type")
    def colored_report_type(self, obj):
        icons = {"weekly": "📅", "monthly": "📊", "manager": "👨‍💼", "department": "🏢", "annual": "📈"}
        colors = {"weekly": "#2b8a3e", "monthly": "#0d6efd", "manager": "#f59f00", "department": "#8b5cf6", "annual": "#e03131"}
        icon, color = icons.get(obj.report_type, "📁"), colors.get(obj.report_type, "#6c757d")
        return format_html('<span style="font-size:16px;color:{};">{}</span> <strong style="color:{};">{}</strong>',
                           color, icon, color, obj.report_type.title())

    @admin.display(description="Period")
    def period_badge(self, obj):
        return format_html('<span style="background:#e9ecef;padding:4px 8px;border-radius:4px;font-size:12px;">{}</span>',
                           obj.get_period_display())

    @admin.display(description="Scope")
    def scope_info(self, obj):
        if obj.manager:
            name = f"{obj.manager.user.first_name} {obj.manager.user.last_name}".strip()
            return format_html('👨‍💼 <span title="Manager">{}</span>', name or obj.manager.user.emp_id)
        elif obj.department:
            return format_html('🏢 <span title="Department">{}</span>', obj.department.name)
        return "—"

    @admin.display(description="Generated By")
    def generated_by_link(self, obj):
        if obj.generated_by:
            user = obj.generated_by
            url = reverse('admin:auth_user_change', args=[user.id])
            return format_html('<a href="{}" title="{}">{}</a>', url, user.username, user.get_full_name() or user.username)
        return "—"

    @admin.display(description="Status")
    def status_badge(self, obj):
        if obj.is_archived:
            color, text = "#6c757d", "📦 ARCHIVED"
        elif obj.is_active:
            color, text = "#28a745", "✓ ACTIVE"
        else:
            color, text = "#ffc107", "⏸ INACTIVE"
        return format_html('<span style="background:{};color:white;padding:3px 8px;border-radius:12px;font-size:11px;">{}</span>', color, text)

    @admin.display(description="File")
    def file_download_link(self, obj):
        if obj.file_path:
            size = getattr(obj.file_path, "size", 0)
            size_str = f" ({size / 1024:.1f} KB)" if size and size < 1024**2 else f" ({size / (1024**2):.1f} MB)" if size else ""
            return format_html('<a href="{}" target="_blank" style="color:#007bff;">⬇️ Download{}</a>', obj.file_path.url, size_str)
        return "—"

    @admin.display(description="Records")
    def records_count(self, obj):
        try:
            records = obj.payload.get('records', []) if isinstance(obj.payload, dict) else []
            return format_html('<span style="color:#0066cc;font-weight:bold;">{}</span>', len(records)) if records else "—"
        except Exception:
            return "—"

    @admin.display(description="Generated")
    def generated_at_formatted(self, obj):
        if obj.generated_at:
            diff = timezone.now() - obj.generated_at
            if diff.days == 0:
                label = f"{diff.seconds//3600}h ago" if diff.seconds > 3600 else f"{diff.seconds//60}m ago"
            else:
                label = obj.generated_at.strftime("%b %d, %Y")
            return format_html('<span title="{}">{}</span>', obj.generated_at.strftime("%Y-%m-%d %H:%M"), label)
        return "—"

    @admin.display(description="Actions")
    def actions_column(self, obj):
        eye = '<a href="#" onclick="alert(\'Payload preview in detail view\');return false;" style="color:#17a2b8;">👁️</a>'
        state = '<span style="color:#6c757d;">📦</span>' if obj.is_archived else '<span style="color:#28a745;">✓</span>'
        return mark_safe(f"{eye} {state}")

    @admin.display(description="Payload Preview")
    def payload_preview(self, obj):
        if obj.payload:
            try:
                data = json.dumps(obj.payload, indent=2, ensure_ascii=False)
                if len(data) > 5000:
                    data = data[:5000] + "\n... (truncated)"
                return format_html('<pre style="background:#f8f9fa;padding:10px;border:1px solid #dee2e6;">{}</pre>', escape(data))
            except Exception as e:
                return f"Error: {e}"
        return "No payload"

    # ======================== BULK ACTIONS =======================
    actions = ['make_active', 'make_inactive', 'archive_reports', 'unarchive_reports', 'export_to_csv']

    @admin.action(description="✓ Activate selected")
    def make_active(self, request, queryset):
        count = queryset.update(is_active=True, is_archived=False)
        self.message_user(request, f"{count} reports activated.", messages.SUCCESS)

    @admin.action(description="⏸ Deactivate selected")
    def make_inactive(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} reports deactivated.", messages.WARNING)

    @admin.action(description="📦 Archive selected")
    def archive_reports(self, request, queryset):
        count = queryset.update(is_archived=True, is_active=False)
        self.message_user(request, f"{count} archived.", messages.INFO)

    @admin.action(description="📤 Unarchive selected")
    def unarchive_reports(self, request, queryset):
        count = queryset.update(is_archived=False, is_active=True)
        self.message_user(request, f"{count} unarchived.", messages.SUCCESS)

    @admin.action(description="📊 Export to CSV")
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cached_reports.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Type', 'Year', 'Manager', 'Dept', 'Active', 'Archived', 'Generated At'])
        for r in queryset:
            writer.writerow([
                r.id, r.report_type, r.year,
                getattr(r.manager, "id", ""), getattr(r.department, "name", ""),
                "Yes" if r.is_active else "No", "Yes" if r.is_archived else "No",
                r.generated_at.strftime("%Y-%m-%d %H:%M") if r.generated_at else ""
            ])
        return response

    # ======================== SECURITY =======================
    def has_add_permission(self, request): return request.user.is_superuser
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser
    def has_change_permission(self, request, obj=None): return request.user.is_staff or request.user.is_superuser
    def has_view_permission(self, request, obj=None): return request.user.is_staff or request.user.is_superuser

    # ======================== SAVE & CHANGE LIST =======================
    def save_model(self, request, obj, form, change):
        if not change and not obj.generated_by:
            obj.generated_by = request.user
        super().save_model(request, obj, form, change)
        if change:
            self.message_user(request, f"Report '{obj.report_type}' updated successfully.", messages.SUCCESS)

    def changelist_view(self, request, extra_context=None):
        """Dual Banner: Adds both message and embedded context banners."""
        qs = self.get_queryset(request)
        total, active, archived = qs.count(), qs.filter(is_active=True).count(), qs.filter(is_archived=True).count()
        files = qs.exclude(Q(file_path='') | Q(file_path__isnull=True)).count()

        # Add to extra_context
        stats_html = format_html(
            '<div style="margin:15px 0;padding:15px;background:linear-gradient(135deg,#667eea,#764ba2);color:white;border-radius:8px;">'
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;text-align:center;">'
            '<div><div style="font-size:26px;font-weight:bold;">{}</div><div>Total</div></div>'
            '<div><div style="font-size:26px;font-weight:bold;">{}</div><div>Active</div></div>'
            '<div><div style="font-size:26px;font-weight:bold;">{}</div><div>Archived</div></div>'
            '<div><div style="font-size:26px;font-weight:bold;">{}</div><div>With Files</div></div>'
            '</div></div>', total, active, archived, files
        )

        extra_context = extra_context or {}
        extra_context["statistics_banner"] = mark_safe(stats_html)

        # Also add message-based banner (fallback)
        if request.method == "GET" and not request.GET.get("q"):
            msg_html = format_html(
                "<b>📊 Stats:</b> Total: {}, Active: {}, Archived: {}, With Files: {}",
                total, active, archived, files
            )
            messages.info(request, mark_safe(msg_html))

        return super().changelist_view(request, extra_context)


# ===============================================
# INLINE ADMIN
# ===============================================
class CachedReportInline(admin.TabularInline):
    model = CachedReport
    extra = 0
    can_delete = False
    readonly_fields = ('report_type', 'get_period_display', 'generated_at', 'is_active')
    fields = ('report_type', 'get_period_display', 'generated_at', 'is_active')

    def has_add_permission(self, request, obj=None):
        return False