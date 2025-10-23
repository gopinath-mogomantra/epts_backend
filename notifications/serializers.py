# ===============================================
# notifications/serializers.py
# ===============================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification
from employee.serializers import UserSummarySerializer

User = get_user_model()


# ===============================================================
# Notification Serializer (Unified for Both Modes)
# ===============================================================
class NotificationSerializer(serializers.ModelSerializer):
    """
    Handles both 'auto-delete' and 'persistent' notifications.
    Includes employee user summary and formatted timestamps.
    """
    employee = UserSummarySerializer(read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    read_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True, required=False)

    class Meta:
        model = Notification
        fields = [
            "id",
            "employee",
            "message",
            "is_read",
            "created_at",
            "read_at",
            "auto_delete",
        ]
        read_only_fields = ["id", "employee", "created_at", "read_at", "is_read"]
