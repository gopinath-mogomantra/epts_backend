# ===============================================
# notifications/admin.py
# ===============================================
"""
Django Admin configuration for Notifications.

Features:
- Rich list display with priority and category indicators
- Advanced filtering (priority, category, status, date)
- Bulk actions (mark as read, delete, change priority)
- Inline employee and department info
- Custom admin actions
- Export functionality
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Q, Count
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponse
import csv
from datetime import timedelta

from .models import Notification


# ===========================================================
# Custom Filters
# ===========================================================

class PriorityFilter(admin.SimpleListFilter):
    """Filter notifications by priority with visual indicators."""
    title = 'Priority'
    parameter_name = 'priority'

    def lookups(self, request, model_admin):
        return [
            ('urgent', '🔴 Urgent'),
            ('high', '🟠 High'),
            ('medium', '🟡 Medium'),
            ('low', '🔵 Low'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(priority=self.value())
        return queryset


class ReadStatusFilter(admin.SimpleListFilter):
    """Filter by read status."""
    title = 'Read Status'
    parameter_name = 'read_status'

    def lookups(self, request, model_admin):
        return [
            ('unread', '◯ Unread'),
            ('read', '✓ Read'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'unread':
            return queryset.filter(is_read=False)
        elif self.value() == 'read':
            return queryset.filter(is_read=True)
        return queryset


class ExpirationFilter(admin.SimpleListFilter):
    """Filter by expiration status."""
    title = 'Expiration Status'
    parameter_name = 'expiration'

    def lookups(self, request, model_admin):
        return [
            ('active', 'Active (Not Expired)'),
            ('expired', 'Expired'),
            ('expiring_soon', 'Expiring Soon (< 24h)'),
            ('no_expiry', 'No Expiration'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        
        if self.value() == 'active':
            return queryset.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=now)
            )
        elif self.value() == 'expired':
            return queryset.filter(expires_at__lte=now)
        elif self.value() == 'expiring_soon':
            tomorrow = now + timedelta(hours=24)
            return queryset.filter(
                expires_at__gt=now,
                expires_at__lte=tomorrow
            )
        elif self.value() == 'no_expiry':
            return queryset.filter(expires_at__isnull=True)
        
        return queryset


class DateRangeFilter(admin.SimpleListFilter):
    """Filter notifications by date range."""
    title = 'Date Range'
    parameter_name = 'date_range'

    def lookups(self, request, model_admin):
        return [
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('older', 'Older than 1 Month'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if self.value() == 'today':
            return queryset.filter(created_at__gte=today_start)
        elif self.value() == 'yesterday':
            yesterday_start = today_start - timedelta(days=1)
            return queryset.filter(
                created_at__gte=yesterday_start,
                created_at__lt=today_start
            )
        elif self.value() == 'week':
            week_start = today_start - timedelta(days=today_start.weekday())
            return queryset.filter(created_at__gte=week_start)
        elif self.value() == 'month':
            month_start = today_start.replace(day=1)
            return queryset.filter(created_at__gte=month_start)
        elif self.value() == 'older':
            month_ago = today_start - timedelta(days=30)
            return queryset.filter(created_at__lt=month_ago)
        
        return queryset


# ===========================================================
# Main Admin Configuration
# ===========================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for the Notification model.
    """
    
    # =======================================================
    # List Display Configuration
    # =======================================================
    list_display = (
        "id",
        "priority_indicator",
        "category_indicator",
        "get_emp_id",
        "get_employee_name",
        "truncated_message",
        "status_indicator",
        "auto_delete_indicator",
        "created_at_display",
        "expiration_display",
    )
    
    list_display_links = ("id", "truncated_message")
    
    # =======================================================
    # Filters and Search
    # =======================================================
    list_filter = (
        PriorityFilter,
        ReadStatusFilter,
        ExpirationFilter,
        DateRangeFilter,
        "category",
        "auto_delete",
        "department",
    )
    
    search_fields = (
        "employee__email",
        "employee__first_name",
        "employee__last_name",
        "employee__username",
        "employee__emp_id",
        "message",
        "department__name",
    )
    
    # =======================================================
    # Ordering and Pagination
    # =======================================================
    ordering = ("-priority", "-created_at")
    list_per_page = 25
    
    # =======================================================
    # Detail Page Configuration
    # =======================================================
    fieldsets = (
        ("Recipient Information", {
            "fields": ("employee", "department"),
        }),
        ("Notification Content", {
            "fields": ("message", "link", "category", "priority"),
        }),
        ("Status & Behavior", {
            "fields": ("is_read", "auto_delete", "expires_at"),
        }),
        ("Metadata", {
            "fields": ("metadata",),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("created_at", "read_at"),
            "classes": ("collapse",),
        }),
    )
    
    readonly_fields = ("created_at", "read_at")
    
    # =======================================================
    # Autocomplete and Widgets
    # =======================================================
    autocomplete_fields = ["employee", "department"]
    
    # =======================================================
    # Custom Actions
    # =======================================================
    actions = [
        "mark_as_read_action",
        "mark_as_unread_action",
        "delete_selected_action",
        "change_to_urgent_action",
        "change_to_high_action",
        "extend_expiration_action",
        "export_to_csv_action",
    ]
    
    # =======================================================
    # Custom Display Methods
    # =======================================================
    
    @admin.display(description="Priority", ordering="priority")
    def priority_indicator(self, obj):
        """Display priority with colored badge."""
        colors = {
            Notification.PRIORITY_URGENT: "#dc3545",  # Red
            Notification.PRIORITY_HIGH: "#fd7e14",    # Orange
            Notification.PRIORITY_MEDIUM: "#ffc107",  # Yellow
            Notification.PRIORITY_LOW: "#0dcaf0",     # Blue
        }
        
        icons = {
            Notification.PRIORITY_URGENT: "🔴",
            Notification.PRIORITY_HIGH: "🟠",
            Notification.PRIORITY_MEDIUM: "🟡",
            Notification.PRIORITY_LOW: "🔵",
        }
        
        color = colors.get(obj.priority, "#6c757d")
        icon = icons.get(obj.priority, "⚪")
        label = obj.get_priority_display()
        
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 8px; border-radius: 3px; font-size: 11px;">'
            '{} {}</span>',
            color, icon, label
        )
    
    @admin.display(description="Category", ordering="category")
    def category_indicator(self, obj):
        """Display category with icon."""
        icons = {
            Notification.CATEGORY_PERFORMANCE: "📊",
            Notification.CATEGORY_FEEDBACK: "💬",
            Notification.CATEGORY_SYSTEM: "⚙️",
            Notification.CATEGORY_ATTENDANCE: "📅",
            Notification.CATEGORY_LEAVE: "🏖️",
            Notification.CATEGORY_ANNOUNCEMENT: "📢",
        }
        
        icon = icons.get(obj.category, "📢")
        label = obj.get_category_display()
        
        return format_html(
            '<span style="font-size: 14px;">{} {}</span>',
            icon, label
        )
    
    @admin.display(description="Status")
    def status_indicator(self, obj):
        """Display read status with visual indicator."""
        if obj.is_expired:
            return format_html(
                '<span style="color: #6c757d;">⏱️ Expired</span>'
            )
        elif obj.is_read:
            return format_html(
                '<span style="color: #198754;">✓ Read</span>'
            )
        else:
            return format_html(
                '<span style="color: #0d6efd; font-weight: bold;">◯ Unread</span>'
            )
    
    @admin.display(description="Auto-Delete")
    def auto_delete_indicator(self, obj):
        """Display auto-delete status."""
        if obj.auto_delete:
            return format_html(
                '<span style="color: #dc3545;">🗑️ Yes</span>'
            )
        else:
            return format_html(
                '<span style="color: #198754;">💾 No</span>'
            )
    
    @admin.display(description="Emp ID")
    def get_emp_id(self, obj):
        """Display employee ID with link."""
        emp_id = getattr(obj.employee, "emp_id", None)
        if emp_id:
            return emp_id
        return "-"
    
    @admin.display(description="Employee", ordering="employee__username")
    def get_employee_name(self, obj):
        """Display employee name with link to user admin."""
        if obj.employee:
            first = getattr(obj.employee, "first_name", "")
            last = getattr(obj.employee, "last_name", "")
            name = f"{first} {last}".strip() or obj.employee.username
            
            # Create link to user admin
            url = reverse("admin:auth_user_change", args=[obj.employee.id])
            return format_html('<a href="{}">{}</a>', url, name)
        return "-"
    
    @admin.display(description="Message")
    def truncated_message(self, obj):
        """Display truncated message with tooltip."""
        max_length = 60
        if len(obj.message) > max_length:
            truncated = obj.message[:max_length] + "..."
            return format_html(
                '<span title="{}">{}</span>',
                obj.message,
                truncated
            )
        return obj.message
    
    @admin.display(description="Created", ordering="created_at")
    def created_at_display(self, obj):
        """Display creation time with relative time."""
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            relative = f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            relative = f"{hours}h ago"
        else:
            minutes = diff.seconds // 60
            relative = f"{minutes}m ago"
        
        formatted = obj.created_at.strftime("%Y-%m-%d %H:%M")
        
        return format_html(
            '<span title="{}">{}</span>',
            formatted,
            relative
        )
    
    @admin.display(description="Expiration", ordering="expires_at")
    def expiration_display(self, obj):
        """Display expiration status."""
        if not obj.expires_at:
            return format_html('<span style="color: #6c757d;">-</span>')
        
        if obj.is_expired:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">⏱️ Expired</span>'
            )
        
        now = timezone.now()
        diff = obj.expires_at - now
        
        if diff.days > 0:
            return format_html(
                '<span style="color: #198754;">In {}d</span>',
                diff.days
            )
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return format_html(
                '<span style="color: #ffc107;">In {}h</span>',
                hours
            )
        else:
            minutes = diff.seconds // 60
            return format_html(
                '<span style="color: #fd7e14; font-weight: bold;">In {}m</span>',
                minutes
            )
    
    # =======================================================
    # Custom Actions
    # =======================================================
    
    @admin.action(description="✓ Mark selected as read")
    def mark_as_read_action(self, request, queryset):
        """Mark selected notifications as read."""
        unread = queryset.filter(is_read=False)
        count = unread.count()
        
        # Update non-auto-delete notifications
        persistent = unread.filter(auto_delete=False)
        updated = persistent.update(is_read=True, read_at=timezone.now())
        
        # Delete auto-delete notifications
        auto_delete = unread.filter(auto_delete=True)
        deleted = auto_delete.count()
        auto_delete.delete()
        
        self.message_user(
            request,
            f"Marked {updated} notification(s) as read and deleted {deleted} auto-delete notification(s).",
            messages.SUCCESS
        )
    
    @admin.action(description="◯ Mark selected as unread")
    def mark_as_unread_action(self, request, queryset):
        """Mark selected notifications as unread."""
        # Only mark persistent notifications as unread
        persistent = queryset.filter(is_read=True, auto_delete=False)
        count = persistent.update(is_read=False, read_at=None)
        
        self.message_user(
            request,
            f"Marked {count} persistent notification(s) as unread.",
            messages.SUCCESS
        )
        
        if queryset.filter(auto_delete=True).exists():
            self.message_user(
                request,
                "Auto-delete notifications cannot be marked as unread.",
                messages.WARNING
            )
    
    @admin.action(description="🗑️ Delete selected notifications")
    def delete_selected_action(self, request, queryset):
        """Delete selected notifications."""
        count = queryset.count()
        queryset.delete()
        
        self.message_user(
            request,
            f"Deleted {count} notification(s).",
            messages.SUCCESS
        )
    
    @admin.action(description="🔴 Change priority to Urgent")
    def change_to_urgent_action(self, request, queryset):
        """Change priority to urgent."""
        count = queryset.update(priority=Notification.PRIORITY_URGENT)
        
        self.message_user(
            request,
            f"Changed {count} notification(s) to Urgent priority.",
            messages.SUCCESS
        )
    
    @admin.action(description="🟠 Change priority to High")
    def change_to_high_action(self, request, queryset):
        """Change priority to high."""
        count = queryset.update(priority=Notification.PRIORITY_HIGH)
        
        self.message_user(
            request,
            f"Changed {count} notification(s) to High priority.",
            messages.SUCCESS
        )
    
    @admin.action(description="⏰ Extend expiration by 7 days")
    def extend_expiration_action(self, request, queryset):
        """Extend expiration by 7 days."""
        now = timezone.now()
        extension = timedelta(days=7)
        count = 0
        
        for notification in queryset:
            if notification.expires_at:
                notification.expires_at += extension
            else:
                notification.expires_at = now + extension
            notification.save(update_fields=['expires_at'])
            count += 1
        
        self.message_user(
            request,
            f"Extended expiration for {count} notification(s) by 7 days.",
            messages.SUCCESS
        )
    
    @admin.action(description="📥 Export to CSV")
    def export_to_csv_action(self, request, queryset):
        """Export selected notifications to CSV."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="notifications.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Employee ID', 'Employee Name', 'Message', 'Category',
            'Priority', 'Is Read', 'Auto Delete', 'Created At', 'Expires At'
        ])
        
        for notification in queryset:
            emp_id = getattr(notification.employee, 'emp_id', '')
            emp_name = notification.employee.get_full_name() or notification.employee.username
            
            writer.writerow([
                notification.id,
                emp_id,
                emp_name,
                notification.message,
                notification.get_category_display(),
                notification.get_priority_display(),
                'Yes' if notification.is_read else 'No',
                'Yes' if notification.auto_delete else 'No',
                notification.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                notification.expires_at.strftime('%Y-%m-%d %H:%M:%S') if notification.expires_at else '',
            ])
        
        self.message_user(
            request,
            f"Exported {queryset.count()} notification(s) to CSV.",
            messages.SUCCESS
        )
        
        return response
    
    # =======================================================
    # Custom Queryset Optimization
    # =======================================================
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('employee', 'department')
    
    # =======================================================
    # Changelist View Customization
    # =======================================================
    
    def changelist_view(self, request, extra_context=None):
        """Add statistics to changelist view."""
        extra_context = extra_context or {}
        
        # Get notification statistics
        qs = self.get_queryset(request)
        
        extra_context['total_notifications'] = qs.count()
        extra_context['unread_count'] = qs.filter(is_read=False).count()
        extra_context['urgent_count'] = qs.filter(
            priority=Notification.PRIORITY_URGENT
        ).count()
        extra_context['expired_count'] = qs.filter(
            expires_at__lte=timezone.now()
        ).count()
        
        return super().changelist_view(request, extra_context)


# ===========================================================
# Usage Tips
# ===========================================================
"""
Admin Interface Features:

1. List View:
   - Color-coded priority badges (🔴 🟠 🟡 🔵)
   - Category icons (📊 💬 ⚙️ 📅 🏖️ 📢)
   - Status indicators (✓ Read, ◯ Unread, ⏱️ Expired)
   - Relative time display (2h ago, 3d ago)
   - Clickable employee links

2. Filters:
   - Priority (Urgent, High, Medium, Low)
   - Read Status (Read, Unread)
   - Expiration (Active, Expired, Expiring Soon, No Expiry)
   - Date Range (Today, This Week, This Month, Older)
   - Category (Performance, Feedback, System, etc.)
   - Auto-delete status

3. Search:
   - Employee name, email, username, emp_id
   - Message content
   - Department name

4. Bulk Actions:
   - Mark as read/unread
   - Delete notifications
   - Change priority (Urgent, High)
   - Extend expiration
   - Export to CSV

5. Detail Page:
   - Organized fieldsets
   - Autocomplete for employee and department
   - Readonly timestamp fields
   - Collapsible metadata and timestamps
"""