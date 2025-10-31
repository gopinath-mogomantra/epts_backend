# ===========================================================
# notifications/serializers.py (Final — Fully Optimized)
# ===========================================================
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification
from employee.serializers import UserSummarySerializer

User = get_user_model()


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model.
    Supports both user-triggered and system-triggered notifications.

    Frontend display structure:
    - Notification dropdown icon
    - Status badges (Read / Unread)
    - Timestamp formatting for UI
    """

    # 🔹 Nested employee info (receiver)
    employee = UserSummarySerializer(read_only=True)

    # 🔹 Readable department name (for broadcast messages)
    department_name = serializers.CharField(
        source="department.name", read_only=True, default=None
    )

    # 🔹 Computed UI helper fields
    status_display = serializers.SerializerMethodField()
    meta_display = serializers.SerializerMethodField()
    category_icon = serializers.SerializerMethodField()

    # 🔹 Formatted timestamps
    created_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", read_only=True
    )
    read_at = serializers.DateTimeField(
        format="%Y-%m-%d %H:%M:%S", read_only=True, required=False
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "employee",
            "department_name",
            "message",
            "link",
            "category",
            "category_icon",
            "is_read",
            "status_display",
            "meta_display",
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
            "meta_display",
            "category_icon",
            "link",
        ]

    # -------------------------------------------------------
    # 🧩 Computed Field Methods
    # -------------------------------------------------------
    def get_status_display(self, obj):
        """Return status text for frontend tags."""
        if obj.is_read:
            return "Read & Auto-Deleted" if obj.auto_delete else "Read"
        return "Unread"

    def get_meta_display(self, obj):
        """
        Short message for frontend notification dropdown.
        Example:
        "📊 Performance updated (28 Oct 2025, 11:24)"
        """
        icon = self.get_category_icon(obj)
        ts = obj.created_at.strftime("%d %b %Y, %H:%M")
        return f"{icon} {obj.message} ({ts})"

    def get_category_icon(self, obj):
        """Map category to emoji/icon for UI clarity."""
        icon_map = {
            "performance": "📊",
            "feedback": "💬",
            "system": "⚙️",
            "alert": "🚨",
        }
        return icon_map.get(obj.category, "📢")

    # -------------------------------------------------------
    # 🧠 Auto-assign User + Department
    # -------------------------------------------------------
    def create(self, validated_data):
        """
        Auto-assign employee to logged-in user (if missing).
        Auto-fill department from employee profile.
        """
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data.setdefault("employee", request.user)
            if not validated_data.get("department") and hasattr(request.user, "employee"):
                validated_data["department"] = getattr(request.user.employee, "department", None)

        return super().create(validated_data)
