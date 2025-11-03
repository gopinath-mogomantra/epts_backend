# ===========================================================
# feedback/admin.py (Enhanced)
# ===========================================================
"""
Enhanced Django admin for feedback models.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback


class BaseFeedbackAdmin(admin.ModelAdmin):
    """Base admin configuration for all feedback types."""
    
    list_display = (
        "id",
        "priority_indicator",
        "employee_name",
        "rating_display",
        "status_badge",
        "sentiment_icon",
        "acknowledged_indicator",
        "created_at_display",
    )
    
    list_filter = (
        "priority",
        "status",
        "sentiment",
        "acknowledged",
        "requires_action",
        "visibility",
        "feedback_date",
    )
    
    search_fields = (
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__emp_id",
        "feedback_text",
        "tags",
    )
    
    readonly_fields = (
        "created_at",
        "updated_at",
        "acknowledged_at",
        "response_date",
        "action_completed_at",
    )
    
    ordering = ("-priority", "-feedback_date", "-created_at")
    
    def priority_indicator(self, obj):
        colors = {
            'urgent': "#dc3545",
            'high': "#fd7e14",
            'normal': "#ffc107",
            'low': "#0dcaf0",
        }
        icons = {'urgent': "🔴", 'high': "🟠", 'normal': "🟡", 'low': "🔵"}
        
        color = colors.get(obj.priority, "#6c757d")
        icon = icons.get(obj.priority, "⚪")
        
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            '{} {}</span>',
            color, icon, obj.get_priority_display()
        )
    priority_indicator.short_description = "Priority"
    
    def employee_name(self, obj):
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            name = f"{u.first_name} {u.last_name}".strip() or u.username
            return format_html('<strong>{}</strong> ({})', name, u.emp_id)
        return "-"
    employee_name.short_description = "Employee"
    
    def rating_display(self, obj):
        color = "#198754" if obj.rating >= 8 else "#ffc107" if obj.rating >= 5 else "#dc3545"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}/10</span>',
            color, obj.rating
        )
    rating_display.short_description = "Rating"
    
    def status_badge(self, obj):
        colors = {
            'pending': "#6c757d",
            'reviewed': "#0d6efd",
            'acknowledged': "#198754",
            'actioned': "#20c997",
            'archived': "#adb5bd",
        }
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 6px; border-radius: 3px; font-size: 10px;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    
    def sentiment_icon(self, obj):
        icons = {'positive': "😊", 'neutral': "😐", 'negative': "😟", 'mixed': "🤔"}
        return icons.get(obj.sentiment, "😐")
    sentiment_icon.short_description = "Sentiment"
    
    def acknowledged_indicator(self, obj):
        if obj.acknowledged:
            return format_html('<span style="color: #198754;">✓ Yes</span>')
        return format_html('<span style="color: #dc3545;">◯ No</span>')
    acknowledged_indicator.short_description = "Ack'd"
    
    def created_at_display(self, obj):
        return obj.created_at.strftime("%Y-%m-%d %H:%M")
    created_at_display.short_description = "Created"
    created_at_display.admin_order_field = "created_at"


@admin.register(GeneralFeedback)
class GeneralFeedbackAdmin(BaseFeedbackAdmin):
    """Admin for General Feedback."""
    
    fieldsets = (
        ("Employee Information", {
            "fields": ("employee", "department")
        }),
        ("Feedback Content", {
            "fields": ("feedback_text", "remarks", "rating", "feedback_category", "tags")
        }),
        ("Priority & Status", {
            "fields": ("priority", "status", "sentiment")
        }),
        ("Acknowledgment", {
            "fields": ("acknowledged", "acknowledged_at", "employee_response", "response_date")
        }),
        ("Action Items", {
            "fields": ("requires_action", "action_items", "action_completed", "action_completed_at")
        }),
        ("Visibility & Access", {
            "fields": ("visibility", "confidential")
        }),
        ("Metadata", {
            "fields": ("created_by", "source_type", "metadata", "feedback_date"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ManagerFeedback)
class ManagerFeedbackAdmin(BaseFeedbackAdmin):
    """Admin for Manager Feedback."""
    
    list_display = BaseFeedbackAdmin.list_display + ("manager_name",)
    
    fieldsets = (
        ("Employee & Manager", {
            "fields": ("employee", "department", "manager_name", "one_on_one_session")
        }),
        ("Feedback Content", {
            "fields": ("feedback_text", "remarks", "rating", "tags")
        }),
        ("Performance Details", {
            "fields": ("strengths", "improvement_areas")
        }),
        ("Priority & Status", {
            "fields": ("priority", "status", "sentiment")
        }),
        ("Acknowledgment", {
            "fields": ("acknowledged", "acknowledged_at", "employee_response", "response_date"),
            "classes": ("collapse",)
        }),
        ("Action Items", {
            "fields": ("requires_action", "action_items", "action_completed", "action_completed_at"),
            "classes": ("collapse",)
        }),
        ("Visibility & Access", {
            "fields": ("visibility", "confidential")
        }),
        ("Metadata", {
            "fields": ("created_by", "source_type", "metadata", "feedback_date"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ClientFeedback)
class ClientFeedbackAdmin(BaseFeedbackAdmin):
    """Admin for Client Feedback."""
    
    list_display = BaseFeedbackAdmin.list_display + ("client_name", "project_name")
    
    fieldsets = (
        ("Employee & Client", {
            "fields": ("employee", "department", "client_name", "project_name")
        }),
        ("Feedback Content", {
            "fields": ("feedback_text", "remarks", "rating", "would_recommend", "tags")
        }),
        ("Priority & Status", {
            "fields": ("priority", "status", "sentiment")
        }),
        ("Acknowledgment", {
            "fields": ("acknowledged", "acknowledged_at", "employee_response", "response_date"),
            "classes": ("collapse",)
        }),
        ("Action Items", {
            "fields": ("requires_action", "action_items", "action_completed", "action_completed_at"),
            "classes": ("collapse",)
        }),
        ("Visibility & Access", {
            "fields": ("visibility", "confidential")
        }),
        ("Metadata", {
            "fields": ("created_by", "source_type", "metadata", "feedback_date"),
            "classes": ("collapse",)
        }),
    )