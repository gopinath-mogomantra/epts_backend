# ===============================================
# performance/admin.py (Enhanced Version — 01-Nov-2025)
# ===============================================
"""
Django Admin Configuration for Performance Evaluation System

Features:
  ✅ Rich performance metrics visualization
  ✅ Color-coded scores and ratings
  ✅ Rank badges with medal icons
  ✅ Advanced filtering and search
  ✅ Bulk actions for finalization
  ✅ Category-wise score display
  ✅ Export to CSV functionality
  ✅ Inline insights and statistics
  ✅ Performance rating badges
  ✅ Department and weekly grouping
"""
# ===============================================

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.contrib import messages
from django.urls import reverse
import csv
import logging

from .models import PerformanceEvaluation

logger = logging.getLogger(__name__)


# ===============================================
# CUSTOM FILTERS
# ===============================================
class PerformanceRatingFilter(admin.SimpleListFilter):
    """Filter evaluations by performance rating."""
    
    title = "Performance Rating"
    parameter_name = "performance_rating"

    def lookups(self, request, model_admin):
        return (
            ("outstanding", "Outstanding (90-100%)"),
            ("exceeds", "Exceeds Expectations (80-89%)"),
            ("meets", "Meets Expectations (70-79%)"),
            ("needs_improvement", "Needs Improvement (60-69%)"),
            ("unsatisfactory", "Unsatisfactory (<60%)"),
        )

    def queryset(self, request, queryset):
        if self.value() == "outstanding":
            return queryset.filter(average_score__gte=90)
        if self.value() == "exceeds":
            return queryset.filter(average_score__gte=80, average_score__lt=90)
        if self.value() == "meets":
            return queryset.filter(average_score__gte=70, average_score__lt=80)
        if self.value() == "needs_improvement":
            return queryset.filter(average_score__gte=60, average_score__lt=70)
        if self.value() == "unsatisfactory":
            return queryset.filter(average_score__lt=60)


class TopPerformerFilter(admin.SimpleListFilter):
    """Filter top performers by rank."""
    
    title = "Top Performers"
    parameter_name = "top_rank"

    def lookups(self, request, model_admin):
        return (
            ("top3", "Top 3 (🥇🥈🥉)"),
            ("top10", "Top 10"),
            ("top20", "Top 20"),
        )

    def queryset(self, request, queryset):
        if self.value() == "top3":
            return queryset.filter(rank__lte=3)
        if self.value() == "top10":
            return queryset.filter(rank__lte=10)
        if self.value() == "top20":
            return queryset.filter(rank__lte=20)


class FinalizationFilter(admin.SimpleListFilter):
    """Filter by finalization status."""
    
    title = "Finalization Status"
    parameter_name = "finalization"

    def lookups(self, request, model_admin):
        return (
            ("finalized", "Finalized (Locked)"),
            ("draft", "Draft (Editable)"),
        )

    def queryset(self, request, queryset):
        if self.value() == "finalized":
            return queryset.filter(is_finalized=True)
        if self.value() == "draft":
            return queryset.filter(is_finalized=False)


# ===============================================
# PERFORMANCE EVALUATION ADMIN
# ===============================================
@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    """
    Enhanced admin interface for Performance Evaluations.
    
    Features:
      - Visual score indicators
      - Performance rating badges
      - Rank medals for top performers
      - Category breakdowns
      - Bulk finalization
      - CSV export
      - Inline statistics
    """

    # -------------------------------------------------
    # List Display Configuration
    # -------------------------------------------------
    list_display = (
        "get_emp_id",
        "get_employee_name",
        "department_link",
        "evaluation_type_badge",
        "colored_rating",
        "colored_score",
        "total_score",
        "rank_badge",
        "finalized_status",
        "week_year_display",
        "review_date",
    )

    list_display_links = ("get_emp_id", "get_employee_name")

    # -------------------------------------------------
    # Filters (Sidebar)
    # -------------------------------------------------
    list_filter = (
        PerformanceRatingFilter,
        TopPerformerFilter,
        FinalizationFilter,
        "evaluation_type",
        "department",
        "year",
        "week_number",
        "is_finalized",
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
        "department__code",
        "evaluation_type",
        "remarks",
    )

    # -------------------------------------------------
    # Display Settings
    # -------------------------------------------------
    ordering = ("-year", "-week_number", "-average_score")
    list_per_page = 25
    date_hierarchy = "review_date"

    readonly_fields = (
        "total_score",
        "average_score",
        "performance_rating",
        "rank",
        "overall_rank",
        "created_at",
        "updated_at",
        "get_metric_breakdown",
        "get_category_analysis",
        "get_strengths_weaknesses",
        "get_evaluation_summary",
    )

    # -------------------------------------------------
    # Fieldsets (Detail View)
    # -------------------------------------------------
    fieldsets = (
        ("Employee Information", {
            "fields": (
                "employee",
                "evaluator",
                "department",
            )
        }),
        ("Evaluation Period", {
            "fields": (
                "review_date",
                "week_number",
                "year",
                "evaluation_period",
                "evaluation_type",
            )
        }),
        ("Communication & Interpersonal Skills", {
            "fields": (
                "communication_skills",
                "team_skills",
                "cooperation",
                "attitude",
                "professionalism",
            ),
            "classes": ("collapse",),
        }),
        ("Technical & Job Performance", {
            "fields": (
                "technical_skills",
                "job_knowledge",
                "work_quality",
                "work_consistency",
            ),
            "classes": ("collapse",),
        }),
        ("Productivity & Innovation", {
            "fields": (
                "productivity",
                "multitasking",
                "creativity",
            ),
            "classes": ("collapse",),
        }),
        ("Reliability & Attendance", {
            "fields": (
                "dependability",
                "attendance",
                "punctuality",
            ),
            "classes": ("collapse",),
        }),
        ("Calculated Scores", {
            "fields": (
                "total_score",
                "average_score",
                "performance_rating",
                "rank",
                "overall_rank",
            )
        }),
        ("Analysis & Insights", {
            "fields": (
                "get_metric_breakdown",
                "get_category_analysis",
                "get_strengths_weaknesses",
                "get_evaluation_summary",
            ),
            "classes": ("collapse",),
        }),
        ("Additional Information", {
            "fields": (
                "remarks",
                "is_finalized",
                "created_by",
            )
        }),
        ("Audit Trail", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",),
        }),
    )

    # -------------------------------------------------
    # Bulk Actions
    # -------------------------------------------------
    actions = [
        "finalize_evaluations",
        "unfinalize_evaluations",
        "export_to_csv",
        "recalculate_ranks",
    ]

    # -------------------------------------------------
    # Custom Display Methods
    # -------------------------------------------------
    def get_emp_id(self, obj):
        """Display Employee ID with formatting."""
        if obj.employee and obj.employee.user:
            emp_id = getattr(obj.employee.user, "emp_id", "-")
            return format_html(
                '<span style="font-family:monospace; font-weight:bold;">{}</span>',
                emp_id
            )
        return "-"
    
    get_emp_id.short_description = "Employee ID"
    get_emp_id.admin_order_field = "employee__user__emp_id"

    def get_employee_name(self, obj):
        """Display full name of the employee."""
        if obj.employee and obj.employee.user:
            first = obj.employee.user.first_name or ""
            last = obj.employee.user.last_name or ""
            name = f"{first} {last}".strip() or obj.employee.user.username
            return format_html('<strong>{}</strong>', name)
        return "-"
    
    get_employee_name.short_description = "Employee Name"
    get_employee_name.admin_order_field = "employee__user__first_name"

    def department_link(self, obj):
        """Link to department change page."""
        if not obj.department:
            return format_html('<span style="color:#999;">-</span>')
        
        url = reverse("admin:employee_department_change", args=[obj.department.pk])
        return format_html(
            '<a href="{}" style="color:#007bff;">{}</a>',
            url, obj.department.name
        )
    
    department_link.short_description = "Department"
    department_link.admin_order_field = "department__name"

    def evaluation_type_badge(self, obj):
        """Display evaluation type with colored badge."""
        colors = {
            "Admin": "#007bff",
            "Manager": "#28a745",
            "Client": "#ffc107",
            "Self": "#6c757d",
        }
        color = colors.get(obj.evaluation_type, "#999")
        
        return format_html(
            '<span style="background-color:{}; color:white; padding:3px 8px; '
            'border-radius:4px; font-size:11px; font-weight:bold;">{}</span>',
            color, obj.evaluation_type
        )
    
    evaluation_type_badge.short_description = "Evaluation Type"
    evaluation_type_badge.admin_order_field = "evaluation_type"

    def colored_rating(self, obj):
        """Display performance rating with color coding."""
        rating = obj.performance_rating or "N/A"
        
        rating_colors = {
            "Outstanding": ("#28a745", "⭐⭐⭐"),
            "Exceeds Expectations": ("#28a745", "⭐⭐"),
            "Meets Expectations": ("#ffc107", "⭐"),
            "Needs Improvement": ("#fd7e14", "⚠️"),
            "Unsatisfactory": ("#dc3545", "❌"),
        }
        
        color, icon = rating_colors.get(rating, ("#6c757d", ""))
        
        return format_html(
            '<span style="color:{}; font-weight:bold;">{} {}</span>',
            color, icon, rating
        )
    
    colored_rating.short_description = "Rating"
    colored_rating.admin_order_field = "performance_rating"

    def colored_score(self, obj):
        """Display average score with color coding."""
        score = float(obj.average_score or 0)
        
        if score >= 90:
            color = "#28a745"  # Green
            icon = "🟢"
        elif score >= 80:
            color = "#28a745"  # Green
            icon = "🟢"
        elif score >= 70:
            color = "#ffc107"  # Yellow
            icon = "🟡"
        elif score >= 60:
            color = "#fd7e14"  # Orange
            icon = "🟠"
        else:
            color = "#dc3545"  # Red
            icon = "🔴"
        
        return format_html(
            '<span style="color:{}; font-weight:bold; font-size:14px;">{} {:.2f}%</span>',
            color, icon, score
        )
    
    colored_score.short_description = "Average Score"
    colored_score.admin_order_field = "average_score"

    def rank_badge(self, obj):
        """Display rank with medal icons for top performers."""
        if not obj.rank:
            return format_html('<span style="color:#999;">-</span>')
        
        if obj.rank <= 3:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            medal = medals.get(obj.rank, "")
            return format_html(
                '<span style="font-size:18px; font-weight:bold;">{} #{}</span>',
                medal, obj.rank
            )
        elif obj.rank <= 10:
            return format_html(
                '<span style="color:#007bff; font-weight:bold;">🏆 #{}</span>',
                obj.rank
            )
        else:
            return format_html(
                '<span style="color:#666;">#{}</span>',
                obj.rank
            )
    
    rank_badge.short_description = "Dept Rank"
    rank_badge.admin_order_field = "rank"

    def finalized_status(self, obj):
        """Display finalization status."""
        if obj.is_finalized:
            return format_html(
                '<span style="color:green; font-weight:bold;">🔒 Locked</span>'
            )
        return format_html(
            '<span style="color:orange;">✏️ Draft</span>'
        )
    
    finalized_status.short_description = "Status"
    finalized_status.admin_order_field = "is_finalized"

    def week_year_display(self, obj):
        """Display week and year in compact format."""
        return format_html(
            '<span style="font-family:monospace;">W{:02d} / {}</span>',
            obj.week_number, obj.year
        )
    
    week_year_display.short_description = "Week/Year"

    # -------------------------------------------------
    # Inline Information Methods
    # -------------------------------------------------
    def get_metric_breakdown(self, obj):
        """Display all 15 metrics in a formatted table."""
        metrics = {
            "Communication Skills": obj.communication_skills,
            "Team Skills": obj.team_skills,
            "Cooperation": obj.cooperation,
            "Attitude": obj.attitude,
            "Professionalism": obj.professionalism,
            "Technical Skills": obj.technical_skills,
            "Job Knowledge": obj.job_knowledge,
            "Work Quality": obj.work_quality,
            "Work Consistency": obj.work_consistency,
            "Productivity": obj.productivity,
            "Multitasking": obj.multitasking,
            "Creativity": obj.creativity,
            "Dependability": obj.dependability,
            "Attendance": obj.attendance,
            "Punctuality": obj.punctuality,
        }
        
        html = '<table style="width:100%; border-collapse:collapse;">'
        html += '<tr style="background:#f0f0f0;"><th style="padding:8px; text-align:left;">Metric</th>'
        html += '<th style="padding:8px; text-align:center;">Score</th>'
        html += '<th style="padding:8px;">Progress Bar</th></tr>'
        
        for metric, value in metrics.items():
            color = "#28a745" if value >= 80 else "#ffc107" if value >= 60 else "#dc3545"
            html += f'<tr style="border-bottom:1px solid #ddd;">'
            html += f'<td style="padding:8px;">{metric}</td>'
            html += f'<td style="padding:8px; text-align:center; font-weight:bold;">{value}</td>'
            html += f'<td style="padding:8px;">'
            html += f'<div style="background:#e0e0e0; border-radius:4px; overflow:hidden;">'
            html += f'<div style="background:{color}; width:{value}%; height:20px;"></div>'
            html += f'</div></td></tr>'
        
        html += '</table>'
        return mark_safe(html)
    
    get_metric_breakdown.short_description = "Metric Breakdown"

    def get_category_analysis(self, obj):
        """Display category-wise average scores."""
        categories = obj.get_category_averages()
        
        html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:15px;">'
        
        for category, avg_score in categories.items():
            color = "#28a745" if avg_score >= 80 else "#ffc107" if avg_score >= 60 else "#dc3545"
            
            html += f'<div style="border:2px solid {color}; border-radius:8px; padding:12px;">'
            html += f'<div style="font-weight:bold; margin-bottom:8px;">{category}</div>'
            html += f'<div style="font-size:24px; color:{color}; font-weight:bold;">{avg_score:.1f}%</div>'
            html += f'</div>'
        
        html += '</div>'
        return mark_safe(html)
    
    get_category_analysis.short_description = "Category Analysis"

    def get_strengths_weaknesses(self, obj):
        """Display top strengths and weaknesses."""
        analysis = obj.get_strengths_and_weaknesses(top_n=3)
        
        html = '<div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">'
        
        # Strengths
        html += '<div style="border:2px solid #28a745; border-radius:8px; padding:15px;">'
        html += '<h4 style="color:#28a745; margin-top:0;">💪 Top Strengths</h4>'
        html += '<ul style="list-style:none; padding:0;">'
        for metric, score in analysis['strengths']:
            html += f'<li style="padding:5px 0; border-bottom:1px solid #e0e0e0;">'
            html += f'<strong>{metric}</strong>: <span style="color:#28a745; font-weight:bold;">{score}</span>'
            html += f'</li>'
        html += '</ul></div>'
        
        # Weaknesses
        html += '<div style="border:2px solid #fd7e14; border-radius:8px; padding:15px;">'
        html += '<h4 style="color:#fd7e14; margin-top:0;">📈 Areas for Improvement</h4>'
        html += '<ul style="list-style:none; padding:0;">'
        for metric, score in analysis['weaknesses']:
            html += f'<li style="padding:5px 0; border-bottom:1px solid #e0e0e0;">'
            html += f'<strong>{metric}</strong>: <span style="color:#fd7e14; font-weight:bold;">{score}</span>'
            html += f'</li>'
        html += '</ul></div>'
        
        html += '</div>'
        return mark_safe(html)
    
    get_strengths_weaknesses.short_description = "Strengths & Weaknesses"

    def get_evaluation_summary(self, obj):
        """Display comprehensive evaluation summary."""
        html = '<div style="background:#f8f9fa; border-radius:8px; padding:20px;">'
        
        # Header
        html += f'<h3 style="margin-top:0; color:#333;">Evaluation Summary</h3>'
        
        # Key Metrics
        html += '<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:15px; margin-bottom:20px;">'
        
        metrics = [
            ("Total Score", f"{obj.total_score}/1500", "#007bff"),
            ("Average Score", f"{obj.average_score:.2f}%", "#28a745"),
            ("Department Rank", f"#{obj.rank}" if obj.rank else "N/A", "#ffc107"),
            ("Overall Rank", f"#{obj.overall_rank}" if obj.overall_rank else "N/A", "#6c757d"),
        ]
        
        for label, value, color in metrics:
            html += f'<div style="text-align:center; padding:15px; background:white; border-radius:6px; border:2px solid {color};">'
            html += f'<div style="font-size:11px; color:#666; margin-bottom:5px;">{label}</div>'
            html += f'<div style="font-size:20px; font-weight:bold; color:{color};">{value}</div>'
            html += f'</div>'
        
        html += '</div>'
        
        # Additional Info
        html += '<div style="margin-top:15px; padding:15px; background:white; border-radius:6px;">'
        html += f'<p><strong>Rating:</strong> {obj.performance_rating}</p>'
        html += f'<p><strong>Evaluation Period:</strong> {obj.evaluation_period}</p>'
        html += f'<p><strong>Evaluator:</strong> {obj.evaluator.get_full_name() if obj.evaluator else "N/A"}</p>'
        html += f'<p><strong>Finalized:</strong> {"Yes 🔒" if obj.is_finalized else "No ✏️"}</p>'
        html += '</div>'
        
        html += '</div>'
        return mark_safe(html)
    
    get_evaluation_summary.short_description = "Evaluation Summary"

    # -------------------------------------------------
    # Bulk Actions
    # -------------------------------------------------
    @admin.action(description="🔒 Finalize selected evaluations")
    def finalize_evaluations(self, request, queryset):
        """Bulk finalize evaluations."""
        updated = 0
        for evaluation in queryset.filter(is_finalized=False):
            evaluation.finalize()
            updated += 1
        
        self.message_user(
            request,
            f"✅ Successfully finalized {updated} evaluation(s).",
            messages.SUCCESS
        )
        logger.info(f"Bulk finalized {updated} evaluations by {request.user.username}")

    @admin.action(description="🔓 Unfinalize selected evaluations (Admin only)")
    def unfinalize_evaluations(self, request, queryset):
        """Bulk unfinalize evaluations (Admin only)."""
        if not request.user.is_superuser:
            self.message_user(
                request,
                "❌ Only superusers can unfinalize evaluations.",
                messages.ERROR
            )
            return
        
        updated = 0
        for evaluation in queryset.filter(is_finalized=True):
            evaluation.unfinalize()
            updated += 1
        
        self.message_user(
            request,
            f"✅ Successfully unlocked {updated} evaluation(s).",
            messages.SUCCESS
        )
        logger.info(f"Bulk unlocked {updated} evaluations by {request.user.username}")

    @admin.action(description="🔄 Recalculate ranks")
    def recalculate_ranks(self, request, queryset):
        """Recalculate ranks for selected evaluations."""
        count = 0
        for evaluation in queryset:
            evaluation.update_ranks()
            evaluation.save(update_fields=['rank', 'overall_rank'])
            count += 1
        
        self.message_user(
            request,
            f"✅ Recalculated ranks for {count} evaluation(s).",
            messages.SUCCESS
        )
        logger.info(f"Ranks recalculated for {count} evaluations by {request.user.username}")

    @admin.action(description="📥 Export to CSV")
    def export_to_csv(self, request, queryset):
        """Export selected evaluations to CSV."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="performance_evaluations.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            "Employee ID", "Employee Name", "Department", "Evaluation Type",
            "Week", "Year", "Review Date", "Average Score", "Performance Rating",
            "Rank", "Overall Rank", "Total Score", "Finalized", "Remarks"
        ])
        
        for evaluation in queryset.select_related(
            "employee__user", "department", "evaluator"
        ):
            writer.writerow([
                evaluation.employee.user.emp_id if evaluation.employee else "",
                f"{evaluation.employee.user.first_name} {evaluation.employee.user.last_name}".strip() if evaluation.employee else "",
                evaluation.department.name if evaluation.department else "",
                evaluation.evaluation_type,
                evaluation.week_number,
                evaluation.year,
                evaluation.review_date.strftime("%Y-%m-%d"),
                float(evaluation.average_score),
                evaluation.performance_rating,
                evaluation.rank or "",
                evaluation.overall_rank or "",
                evaluation.total_score,
                "Yes" if evaluation.is_finalized else "No",
                evaluation.remarks or "",
            ])
        
        logger.info(
            f"Exported {queryset.count()} evaluations by {request.user.username}"
        )
        return response

    # -------------------------------------------------
    # Optimization
    # -------------------------------------------------
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "employee__user",
            "department",
            "evaluator",
            "created_by"
        )

    # -------------------------------------------------
    # Custom Save Logic
    # -------------------------------------------------
    def save_model(self, request, obj, form, change):
        """Auto-set created_by on creation."""
        if not change:  # Creating new
            obj.created_by = request.user
        
        super().save_model(request, obj, form, change)
        
        # Recalculate ranks after save
        obj.update_ranks()
        obj.save(update_fields=['rank', 'overall_rank'])
        
        emp_id = obj.employee.user.emp_id if obj.employee else "Unknown"
        if change:
            logger.info(f"Evaluation updated: {emp_id} by {request.user.username}")
        else:
            logger.info(f"Evaluation created: {emp_id} by {request.user.username}")


# ===============================================
# ADMIN SITE CUSTOMIZATION
# ===============================================
admin.site.site_header = "Performance Management System"
admin.site.site_title = "Performance Admin"
admin.site.index_title = "Performance Evaluation Dashboard"