from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification
from employee.serializers import UserSummarySerializer

User = get_user_model()


# ===========================================================
# ✅ Notification Serializer (Detailed View)
# ===========================================================
class NotificationSerializer(serializers.ModelSerializer):
    """
    Main serializer for Notification model.

    Features:
    - Handles both auto-delete and persistent notifications.
    - Includes employee and department summary.
    - Adds readable timestamps and display text for UI.
    """

    # 🔹 Nested user summary for frontend dashboards
    employee = UserSummarySerializer(read_only=True)

    # 🔹 Derived fields
    department_name = serializers.CharField(
        source="department.name", read_only=True, default=None
    )
    status_display = serializers.SerializerMethodField()
    meta_display = serializers.SerializerMethodField()

    # 🔹 Timestamp formatting (ISO + readable)
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
        ]

    # -------------------------------------------------------
    # ✅ Custom Computed Fields
    # -------------------------------------------------------
    def get_status_display(self, obj):
        """Return human-readable status text."""
        if obj.is_read:
            return "Read & Auto-Deleted" if obj.auto_delete else "Read"
        return "Unread"

    def get_meta_display(self, obj):
        """
        Return a concise summary line for UI cards (e.g. notifications bell).
        Example: "📢 New feedback received (27 Oct 2025, 10:32)"
        """
        icon = "📢" if not obj.is_read else "✅"
        ts = obj.created_at.strftime("%d %b %Y, %H:%M")
        return f"{icon} {obj.message} ({ts})"

    # -------------------------------------------------------
    # ✅ Safe Create Logic (System & Authenticated User)
    # -------------------------------------------------------
    def create(self, validated_data):
        """
        Auto-assigns employee (if not provided) and infers department.
        Used by system-triggered or authenticated notifications.
        """
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data.setdefault("employee", request.user)

            # Auto-assign department from employee profile if available
            if not validated_data.get("department") and hasattr(request.user, "employee_profile"):
                validated_data["department"] = getattr(request.user.employee_profile, "department", None)

        return super().create(validated_data)
