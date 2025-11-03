# ===========================================================
# notifications/serializers.py 
# ===========================================================
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Notification
from employee.serializers import UserSummarySerializer

User = get_user_model()


class NotificationSerializer(serializers.ModelSerializer):
    """
    Full serializer for Notification model with enhanced features.
    
    Supports:
    - Priority-based display (urgent, high, medium, low)
    - Expiration tracking
    - Rich metadata
    - User-triggered and system-triggered notifications
    - Time-based UI helpers (time_ago, is_recent, etc.)
    
    Frontend display structure:
    - Priority badges with color coding
    - Notification dropdown with icons
    - Status badges (Read / Unread / Expired)
    - Timestamp formatting for UI
    - Expiration warnings
    """

    # =======================================================
    # Nested & Related Fields
    # =======================================================
    employee = UserSummarySerializer(read_only=True)
    employee_id = serializers.IntegerField(write_only=True, required=False)

    department_name = serializers.CharField(
        source="department.name",
        read_only=True,
        allow_null=True,
    )
    
    department_id = serializers.IntegerField(
        write_only=True,
        required=False,
        allow_null=True,
    )

    # =======================================================
    # Computed UI Helper Fields
    # =======================================================
    status_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    priority_badge = serializers.SerializerMethodField()
    category_icon = serializers.SerializerMethodField()
    meta_display = serializers.SerializerMethodField()
    
    # Time-based helpers
    time_ago = serializers.SerializerMethodField()
    is_recent = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    expires_in = serializers.SerializerMethodField()

    # =======================================================
    # Formatted Timestamps
    # =======================================================
    created_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S",
        read_only=True
    )
    read_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S",
        read_only=True,
        required=False,
        allow_null=True,
    )
    expires_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S",
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Notification
        fields = [
            # IDs
            "id",
            "employee_id",
            
            # Core fields
            "employee",
            "department_name",
            "department_id",
            "message",
            "link",
            "category",
            "priority",
            "metadata",
            
            # Status fields
            "is_read",
            "auto_delete",
            
            # Timestamps
            "created_at",
            "read_at",
            "expires_at",
            
            # Computed fields
            "status_display",
            "priority_display",
            "priority_badge",
            "category_icon",
            "meta_display",
            "time_ago",
            "is_recent",
            "is_expired",
            "expires_in",
        ]
        read_only_fields = [
            "id",
            "employee",
            "created_at",
            "read_at",
            "department_name",
            "status_display",
            "priority_display",
            "priority_badge",
            "category_icon",
            "meta_display",
            "time_ago",
            "is_recent",
            "is_expired",
            "expires_in",
        ]

    # =======================================================
    # Status & Priority Display Methods
    # =======================================================
    def get_status_display(self, obj):
        """
        Return status text for frontend tags.
        
        Returns:
            str: Status display text (Unread, Read, Expired, etc.)
        """
        if obj.is_expired:
            return "Expired"
        if obj.is_read:
            return "Read (Auto-Delete)" if obj.auto_delete else "Read"
        return "Unread"

    def get_priority_display(self, obj):
        """
        Return human-readable priority.
        
        Returns:
            str: Priority display text
        """
        return obj.get_priority_display()

    def get_priority_badge(self, obj):
        """
        Return priority with color/icon for frontend badges.
        
        Returns:
            dict: Priority badge configuration
        """
        badge_config = {
            Notification.PRIORITY_URGENT: {
                "icon": "🔴",
                "label": "Urgent",
                "color": "red",
                "class": "badge-urgent"
            },
            Notification.PRIORITY_HIGH: {
                "icon": "🟠",
                "label": "High",
                "color": "orange",
                "class": "badge-high"
            },
            Notification.PRIORITY_MEDIUM: {
                "icon": "🟡",
                "label": "Medium",
                "color": "yellow",
                "class": "badge-medium"
            },
            Notification.PRIORITY_LOW: {
                "icon": "🔵",
                "label": "Low",
                "color": "blue",
                "class": "badge-low"
            },
        }
        return badge_config.get(obj.priority, badge_config[Notification.PRIORITY_MEDIUM])

    def get_category_icon(self, obj):
        """
        Map category to emoji/icon for UI clarity.
        Uses model constants for consistency.
        
        Returns:
            str: Emoji icon for category
        """
        icon_map = {
            Notification.CATEGORY_PERFORMANCE: "📊",
            Notification.CATEGORY_FEEDBACK: "💬",
            Notification.CATEGORY_SYSTEM: "⚙️",
            Notification.CATEGORY_ATTENDANCE: "📅",
            Notification.CATEGORY_LEAVE: "🏖️",
            Notification.CATEGORY_ANNOUNCEMENT: "📢",
        }
        return icon_map.get(obj.category, "📢")

    def get_meta_display(self, obj):
        """
        Formatted message for frontend notification dropdown.
        
        Example: "🔴 📊 Performance updated (28 Oct 2025, 11:24)"
        
        Returns:
            str: Formatted notification display string
        """
        priority_icon = self.get_priority_badge(obj)["icon"]
        category_icon = self.get_category_icon(obj)
        timestamp = obj.created_at.strftime("%d %b %Y, %H:%M")
        
        return f"{priority_icon} {category_icon} {obj.message} ({timestamp})"

    # =======================================================
    # Time-Based Helper Methods
    # =======================================================
    def get_time_ago(self, obj):
        """
        Calculate human-readable time since creation.
        
        Returns:
            str: Time ago string (e.g., "2 hours ago", "3 days ago")
        """
        now = timezone.now()
        diff = now - obj.created_at
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"

    def get_is_recent(self, obj):
        """
        Check if notification was created within last 24 hours.
        
        Returns:
            bool: True if recent
        """
        threshold = timezone.now() - timedelta(hours=24)
        return obj.created_at >= threshold

    def get_is_expired(self, obj):
        """
        Check if notification has expired.
        
        Returns:
            bool: True if expired
        """
        return obj.is_expired

    def get_expires_in(self, obj):
        """
        Calculate time until expiration in human-readable format.
        
        Returns:
            str: Time until expiration or None
        """
        if not obj.expires_at:
            return None
        
        if obj.is_expired:
            return "Expired"
        
        diff = obj.expires_at - timezone.now()
        hours = diff.total_seconds() / 3600
        
        if hours < 1:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif hours < 24:
            return f"{int(hours)} hour{'s' if int(hours) != 1 else ''}"
        else:
            days = int(hours / 24)
            return f"{days} day{'s' if days != 1 else ''}"

    # =======================================================
    # Custom Create & Update Logic
    # =======================================================
    def create(self, validated_data):
        """
        Auto-assign employee to logged-in user if not specified.
        Auto-fill department from employee profile.
        
        Args:
            validated_data: Validated serializer data
            
        Returns:
            Notification: Created notification instance
        """
        request = self.context.get("request")
        
        # Auto-assign employee if not provided
        if request and request.user.is_authenticated:
            if "employee_id" not in validated_data:
                validated_data["employee_id"] = request.user.id
            
            # Auto-assign department if not provided
            if "department_id" not in validated_data:
                try:
                    if hasattr(request.user, "employee") and request.user.employee:
                        validated_data["department_id"] = getattr(
                            request.user.employee, 
                            "department_id", 
                            None
                        )
                except AttributeError:
                    pass

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Handle notification updates with special logic for read status.
        
        Args:
            instance: Notification instance
            validated_data: Validated update data
            
        Returns:
            Notification: Updated notification instance
        """
        # If marking as read, use the model's mark_as_read method
        if "is_read" in validated_data and validated_data["is_read"] and not instance.is_read:
            instance.mark_as_read(auto_commit=False)
            # Remove is_read from validated_data as it's handled by mark_as_read
            validated_data.pop("is_read", None)
        
        return super().update(instance, validated_data)

    def validate_expires_at(self, value):
        """
        Validate that expiration date is in the future.
        
        Args:
            value: Expiration datetime
            
        Returns:
            datetime: Validated expiration datetime
            
        Raises:
            ValidationError: If date is in the past
        """
        if value and value <= timezone.now():
            raise serializers.ValidationError(
                "Expiration date must be in the future."
            )
        return value

    def validate(self, attrs):
        """
        Cross-field validation.
        
        Args:
            attrs: All validated attributes
            
        Returns:
            dict: Validated attributes
        """
        # Ensure read_at is only set when is_read is True
        if attrs.get("read_at") and not attrs.get("is_read"):
            raise serializers.ValidationError({
                "read_at": "read_at can only be set when is_read is True"
            })
        
        return attrs


class NotificationListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for notification lists.
    Excludes heavy nested data and computed fields for better performance.
    """
    
    priority_icon = serializers.SerializerMethodField()
    category_icon = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            "id",
            "message",
            "category",
            "category_icon",
            "priority",
            "priority_icon",
            "is_read",
            "link",
            "created_at",
            "time_ago",
        ]
        read_only_fields = fields

    def get_priority_icon(self, obj):
        """Get priority icon emoji."""
        icons = {
            Notification.PRIORITY_URGENT: "🔴",
            Notification.PRIORITY_HIGH: "🟠",
            Notification.PRIORITY_MEDIUM: "🟡",
            Notification.PRIORITY_LOW: "🔵",
        }
        return icons.get(obj.priority, "⚪")

    def get_category_icon(self, obj):
        """Get category icon emoji."""
        icons = {
            Notification.CATEGORY_PERFORMANCE: "📊",
            Notification.CATEGORY_FEEDBACK: "💬",
            Notification.CATEGORY_SYSTEM: "⚙️",
            Notification.CATEGORY_ATTENDANCE: "📅",
            Notification.CATEGORY_LEAVE: "🏖️",
            Notification.CATEGORY_ANNOUNCEMENT: "📢",
        }
        return icons.get(obj.category, "📢")

    def get_time_ago(self, obj):
        """Simple time ago calculation."""
        now = timezone.now()
        diff = now - obj.created_at
        hours = diff.total_seconds() / 3600
        
        if hours < 1:
            return "Just now"
        elif hours < 24:
            return f"{int(hours)}h ago"
        else:
            days = int(hours / 24)
            return f"{days}d ago"


class NotificationMarkReadSerializer(serializers.Serializer):
    """
    Serializer for marking notifications as read.
    Used in bulk operations.
    """
    
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of notification IDs to mark as read. If empty, marks all as read."
    )
    
    def validate_notification_ids(self, value):
        """Validate that IDs exist and belong to the current user."""
        if not value:
            return value
        
        request = self.context.get("request")
        if not request or not request.user:
            raise serializers.ValidationError("User not authenticated")
        
        # Verify all IDs exist and belong to user
        user_notifications = Notification.objects.filter(
            employee=request.user,
            id__in=value
        )
        
        found_ids = set(user_notifications.values_list("id", flat=True))
        requested_ids = set(value)
        
        if found_ids != requested_ids:
            invalid_ids = requested_ids - found_ids
            raise serializers.ValidationError(
                f"Invalid notification IDs: {invalid_ids}"
            )
        
        return value


class NotificationCreateSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for creating notifications.
    Used by system/admin to create notifications for users.
    """
    
    employee_id = serializers.IntegerField(required=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Notification
        fields = [
            "employee_id",
            "department_id",
            "message",
            "link",
            "category",
            "priority",
            "metadata",
            "auto_delete",
            "expires_at",
        ]
    
    def validate_employee_id(self, value):
        """Validate that employee exists."""
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Employee with ID {value} does not exist")
        return value
    
    def create(self, validated_data):
        """Create notification with validated data."""
        employee_id = validated_data.pop("employee_id")
        department_id = validated_data.pop("department_id", None)
        
        return Notification.objects.create(
            employee_id=employee_id,
            department_id=department_id,
            **validated_data
        )


# =======================================================
# Usage Examples
# =======================================================
"""
Example API responses:

1. List notifications (using NotificationListSerializer):
GET /api/notifications/
{
    "results": [
        {
            "id": 1,
            "message": "Weekly performance report ready",
            "category": "performance",
            "category_icon": "📊",
            "priority": "high",
            "priority_icon": "🟠",
            "is_read": false,
            "link": "/reports/weekly/?week=44",
            "created_at": "2025-10-28T11:24:00",
            "time_ago": "2h ago"
        }
    ]
}

2. Get single notification (using NotificationSerializer):
GET /api/notifications/1/
{
    "id": 1,
    "employee": {"id": 1, "username": "john", "full_name": "John Doe"},
    "message": "Weekly performance report ready",
    "priority": "high",
    "priority_badge": {
        "icon": "🟠",
        "label": "High",
        "color": "orange",
        "class": "badge-high"
    },
    "meta_display": "🟠 📊 Weekly performance report ready (28 Oct 2025, 11:24)",
    "time_ago": "2 hours ago",
    "is_recent": true,
    "expires_in": "6 days"
}

3. Mark as read (using NotificationMarkReadSerializer):
POST /api/notifications/mark-read/
{
    "notification_ids": [1, 2, 3]
}

4. Create notification (using NotificationCreateSerializer):
POST /api/notifications/
{
    "employee_id": 1,
    "message": "New feedback received",
    "category": "feedback",
    "priority": "medium",
    "link": "/feedback/123/"
}
"""