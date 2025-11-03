# ===========================================================
# feedback/serializers.py
# ===========================================================
"""
Enhanced feedback serializers with comprehensive features:
- Multiple serializer types (List, Detail, Create)
- Rich UI helpers
- Validation
- Statistics serializers
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee, Department

User = get_user_model()


# ===========================================================
# Simple User Serializer (Reusable)
# ===========================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    """Lightweight user serializer for nested representations."""
    
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "emp_id", "username", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip() or obj.username


# ===========================================================
# Base Feedback Serializer (Full Detail)
# ===========================================================
class BaseFeedbackSerializer(serializers.ModelSerializer):
    """
    Full-featured base serializer for all feedback types.
    Used for detail views and updates.
    """

    # Foreign keys
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), 
        required=False, 
        allow_null=True
    )
    created_by = SimpleUserSerializer(read_only=True)

    # Computed fields
    employee_full_name = serializers.SerializerMethodField(read_only=True)
    emp_id = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    
    # Display fields
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    sentiment_display = serializers.CharField(source="get_sentiment_display", read_only=True)
    visibility_label = serializers.CharField(source="get_visibility_display", read_only=True)
    
    # UI helpers
    rating_display = serializers.SerializerMethodField(read_only=True)
    priority_badge = serializers.SerializerMethodField(read_only=True)
    sentiment_icon = serializers.SerializerMethodField(read_only=True)
    status_badge = serializers.SerializerMethodField(read_only=True)
    time_ago = serializers.SerializerMethodField(read_only=True)
    
    # Flags
    is_positive = serializers.BooleanField(read_only=True)
    is_negative = serializers.BooleanField(read_only=True)
    is_urgent = serializers.BooleanField(read_only=True)
    needs_attention = serializers.BooleanField(read_only=True)

    class Meta:
        model = None
        fields = [
            # IDs and relationships
            "id",
            "employee",
            "emp_id",
            "employee_full_name",
            "department",
            "department_name",
            
            # Content
            "feedback_text",
            "remarks",
            "rating",
            "rating_display",
            
            # Enhanced fields
            "priority",
            "priority_display",
            "priority_badge",
            "status",
            "status_display",
            "status_badge",
            "sentiment",
            "sentiment_display",
            "sentiment_icon",
            "tags",
            
            # Acknowledgment
            "acknowledged",
            "acknowledged_at",
            "employee_response",
            "response_date",
            
            # Action items
            "requires_action",
            "action_items",
            "action_completed",
            "action_completed_at",
            
            # Visibility
            "visibility",
            "visibility_label",
            "confidential",
            
            # Metadata
            "created_by",
            "source_type",
            "metadata",
            
            # Timestamps
            "feedback_date",
            "created_at",
            "updated_at",
            "time_ago",
            
            # Computed flags
            "is_positive",
            "is_negative",
            "is_urgent",
            "needs_attention",
        ]
        read_only_fields = [
            "created_by", "created_at", "updated_at", "source_type",
            "acknowledged_at", "response_date", "action_completed_at"
        ]

    # =======================================================
    # Computed Field Methods
    # =======================================================
    def get_employee_full_name(self, obj):
        """Return the employee's full name."""
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip() or u.username
        return "-"

    def get_emp_id(self, obj):
        """Return employee emp_id."""
        if obj.employee and obj.employee.user:
            return obj.employee.user.emp_id
        return None

    def get_rating_display(self, obj):
        """Return formatted rating string."""
        return f"{obj.rating}/10"

    def get_priority_badge(self, obj):
        """Return priority with color/icon for frontend badges."""
        badge_config = {
            'urgent': {"icon": "🔴", "label": "Urgent", "color": "red", "class": "badge-urgent"},
            'high': {"icon": "🟠", "label": "High", "color": "orange", "class": "badge-high"},
            'normal': {"icon": "🟡", "label": "Normal", "color": "yellow", "class": "badge-normal"},
            'low': {"icon": "🔵", "label": "Low", "color": "blue", "class": "badge-low"},
        }
        return badge_config.get(obj.priority, badge_config['normal'])

    def get_sentiment_icon(self, obj):
        """Map sentiment to emoji/icon."""
        icon_map = {
            'positive': "😊",
            'neutral': "😐",
            'negative': "😟",
            'mixed': "🤔",
        }
        return icon_map.get(obj.sentiment, "😐")

    def get_status_badge(self, obj):
        """Return status with color for UI."""
        status_config = {
            'pending': {"label": "Pending", "color": "gray", "class": "badge-pending"},
            'reviewed': {"label": "Reviewed", "color": "blue", "class": "badge-reviewed"},
            'acknowledged': {"label": "Acknowledged", "color": "green", "class": "badge-acknowledged"},
            'actioned': {"label": "Action Taken", "color": "success", "class": "badge-actioned"},
            'archived': {"label": "Archived", "color": "secondary", "class": "badge-archived"},
        }
        return status_config.get(obj.status, status_config['pending'])

    def get_time_ago(self, obj):
        """Calculate human-readable time since creation."""
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

    # =======================================================
    # Validation
    # =======================================================
    def validate_rating(self, value):
        """Validate rating is within range."""
        if not (1 <= int(value) <= 10):
            raise serializers.ValidationError("Rating must be between 1 and 10.")
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        employee = attrs.get("employee")
        department = attrs.get("department")

        # Auto-fill department if not provided
        if employee and not department:
            attrs["department"] = employee.department
        # Validate department matches employee
        elif employee and department and employee.department != department:
            raise serializers.ValidationError({
                "department": "Department does not match the employee's assigned department."
            })
        
        return attrs

    # =======================================================
    # Create & Update
    # =======================================================
    def create(self, validated_data):
        """Attach created_by from request context."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        
        return super().create(validated_data)


# ===========================================================
# List Serializer (Lightweight)
# ===========================================================
class BaseFeedbackListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views.
    Optimized for performance with minimal fields.
    """
    
    employee_name = serializers.SerializerMethodField()
    emp_id = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    rating_display = serializers.SerializerMethodField()
    priority_icon = serializers.SerializerMethodField()
    sentiment_icon = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = None
        fields = [
            "id",
            "employee_name",
            "emp_id",
            "department_name",
            "feedback_text",
            "rating",
            "rating_display",
            "priority",
            "priority_icon",
            "status",
            "sentiment",
            "sentiment_icon",
            "acknowledged",
            "requires_action",
            "feedback_date",
            "time_ago",
        ]

    def get_employee_name(self, obj):
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip() or u.username
        return "-"

    def get_emp_id(self, obj):
        return obj.employee.user.emp_id if obj.employee and obj.employee.user else None

    def get_rating_display(self, obj):
        return f"{obj.rating}/10"

    def get_priority_icon(self, obj):
        icons = {'urgent': "🔴", 'high': "🟠", 'normal': "🟡", 'low': "🔵"}
        return icons.get(obj.priority, "⚪")

    def get_sentiment_icon(self, obj):
        icons = {'positive': "😊", 'neutral': "😐", 'negative': "😟", 'mixed': "🤔"}
        return icons.get(obj.sentiment, "😐")

    def get_time_ago(self, obj):
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


# ===========================================================
# Acknowledgment Serializer
# ===========================================================
class FeedbackAcknowledgmentSerializer(serializers.Serializer):
    """Serializer for acknowledging feedback."""
    
    response = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional response from employee"
    )


# ===========================================================
# Action Completion Serializer
# ===========================================================
class FeedbackActionSerializer(serializers.Serializer):
    """Serializer for completing action items."""
    
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Optional notes about action completion"
    )


# ===========================================================
# General Feedback Serializers
# ===========================================================
class GeneralFeedbackSerializer(BaseFeedbackSerializer):
    """Full serializer for General Feedback."""
    
    feedback_category = serializers.CharField(required=False, allow_blank=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = GeneralFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["feedback_category"]


class GeneralFeedbackListSerializer(BaseFeedbackListSerializer):
    """List serializer for General Feedback."""
    
    class Meta(BaseFeedbackListSerializer.Meta):
        model = GeneralFeedback


# ===========================================================
# Manager Feedback Serializers
# ===========================================================
class ManagerFeedbackSerializer(BaseFeedbackSerializer):
    """Full serializer for Manager Feedback."""
    
    manager_full_name = serializers.SerializerMethodField(read_only=True)
    manager_name = serializers.CharField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ManagerFeedback
        fields = BaseFeedbackSerializer.Meta.fields + [
            "manager_name",
            "manager_full_name",
            "one_on_one_session",
            "improvement_areas",
            "strengths",
        ]

    def get_manager_full_name(self, obj):
        """Return manager's name from employee record."""
        if obj.employee and obj.employee.manager and obj.employee.manager.user:
            m = obj.employee.manager.user
            return f"{m.first_name} {m.last_name}".strip() or m.username
        return obj.manager_name or "-"

    def validate(self, attrs):
        """Managers can only submit feedback for their team members."""
        request = self.context.get("request")
        employee = attrs.get("employee")

        if request and getattr(request.user, "role", "") == "Manager":
            try:
                from employee.models import Employee
                manager_emp = Employee.objects.get(user=request.user)
                if employee.manager_id != manager_emp.id:
                    raise serializers.ValidationError({
                        "employee": "Managers can only submit feedback for their own team members."
                    })
            except Employee.DoesNotExist:
                raise serializers.ValidationError({
                    "employee": "Manager record not found for this user."
                })
        
        return super().validate(attrs)


class ManagerFeedbackListSerializer(BaseFeedbackListSerializer):
    """List serializer for Manager Feedback."""
    
    manager_name = serializers.CharField(read_only=True)

    class Meta(BaseFeedbackListSerializer.Meta):
        model = ManagerFeedback
        fields = BaseFeedbackListSerializer.Meta.fields + ["manager_name"]


# ===========================================================
# Client Feedback Serializers
# ===========================================================
class ClientFeedbackSerializer(BaseFeedbackSerializer):
    """Full serializer for Client Feedback."""
    
    client_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    client_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ClientFeedback
        fields = BaseFeedbackSerializer.Meta.fields + [
            "client_name",
            "client_full_name",
            "project_name",
            "would_recommend",
        ]

    def get_client_full_name(self, obj):
        """Return client's name or 'Anonymous Client'."""
        return (obj.client_name or "Anonymous Client").strip()

    def create(self, validated_data):
        """Auto-fill client name if not provided."""
        if not validated_data.get("client_name"):
            validated_data["client_name"] = "Anonymous Client"
        return super().create(validated_data)


class ClientFeedbackListSerializer(BaseFeedbackListSerializer):
    """List serializer for Client Feedback."""
    
    client_name = serializers.CharField(read_only=True)
    project_name = serializers.CharField(read_only=True)

    class Meta(BaseFeedbackListSerializer.Meta):
        model = ClientFeedback
        fields = BaseFeedbackListSerializer.Meta.fields + ["client_name", "project_name"]


# ===========================================================
# Statistics Serializers
# ===========================================================
class FeedbackStatisticsSerializer(serializers.Serializer):
    """Serializer for feedback statistics."""
    
    total = serializers.IntegerField()
    average_rating = serializers.FloatField()
    positive = serializers.IntegerField()
    neutral = serializers.IntegerField()
    negative = serializers.IntegerField()
    acknowledged_count = serializers.IntegerField(required=False)
    requires_action_count = serializers.IntegerField(required=False)


# ===========================================================
# Usage Examples
# ===========================================================
"""
API Usage Examples:

1. List feedback (using lightweight serializer):
GET /api/feedback/general-feedback/
Response: {
    "results": [
        {
            "id": 1,
            "employee_name": "John Doe",
            "rating_display": "8/10",
            "priority_icon": "🟡",
            "sentiment_icon": "😊",
            "time_ago": "2h ago"
        }
    ]
}

2. Get single feedback detail (full serializer):
GET /api/feedback/general-feedback/1/
Response: {
    "id": 1,
    "employee_full_name": "John Doe",
    "priority_badge": {
        "icon": "🟡",
        "label": "Normal",
        "color": "yellow"
    },
    "status_badge": {
        "label": "Pending",
        "color": "gray"
    },
    "needs_attention": false,
    ...
}

3. Acknowledge feedback:
POST /api/feedback/manager-feedback/1/acknowledge/
Body: {
    "response": "Thank you for the feedback. I will work on these areas."
}

4. Complete action:
POST /api/feedback/manager-feedback/1/complete-action/
Body: {
    "notes": "Completed all improvement tasks"
}
"""