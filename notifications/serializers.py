# ===============================================
# notifications/serializers.py (Final Updated Version)
# ===============================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification
from employee.serializers import UserSummarySerializer

User = get_user_model()


# ===============================================================
# Notification Serializer (Unified for Both Auto & Persistent)
# ===============================================================
class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model.
    Supports:
      - Auto-deleting notifications after read
      - Persistent notifications (marked as read)
    Displays employee summary and human-readable timestamps.
    """

    employee = UserSummarySerializer(read_only=True)
    department_name = serializers.CharField(
        source="department.name", read_only=True, default=None
    )
    created_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", read_only=True
    )
    read_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", read_only=True, required=False
    )
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "employee",
            "department_name",
            "message",
            "is_read",
            "status_display",
            "created_at",
            "read_at",
            "auto_delete",
        ]
        read_only_fields = [
            "id",
            "employee",
            "created_at",
            "read_at",
            "is_read",
            "department_name",
            "status_display",
        ]

    # -----------------------------------------------------------
    # Custom Field Logic
    # -----------------------------------------------------------
    def get_status_display(self, obj):
        """Return a readable notification status."""
        if obj.is_read:
            if obj.auto_delete:
                return "Read & Auto-Deleted"
            return "Read"
        return "Unread"

    def create(self, validated_data):
        """
        Automatically assigns employee if not explicitly set.
        Typically used for system-generated notifications.
        """
        request = self.context.get("request")
        if request and request.user.is_authenticated and not validated_data.get("employee"):
            validated_data["employee"] = request.user
        return super().create(validated_data)
