# ===============================================
# feedback/serializers.py
# ===============================================

from rest_framework import serializers
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee, Department
from django.contrib.auth import get_user_model

User = get_user_model()


# ======================================================
# SimpleUserSerializer — Unified for All Roles
# ======================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "role",
        ]

    def get_full_name(self, obj):
        first = obj.first_name or ""
        last = obj.last_name or ""
        return f"{first} {last}".strip()


# ======================================================
# BaseFeedbackSerializer — Shared Logic
# ======================================================
class BaseFeedbackSerializer(serializers.ModelSerializer):
    """
    Base serializer for feedback models.
    Handles shared fields and auto-sets `created_by` user.
    """

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True
    )

    created_by = SimpleUserSerializer(read_only=True)
    employee_full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = None  # defined in subclass
        fields = [
            "id",
            "employee",
            "employee_full_name",
            "department",
            "department_name",
            "feedback_text",
            "remarks",
            "rating",
            "visibility",
            "created_by",
            "feedback_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    # -----------------------------------------------
    # Custom Methods
    # -----------------------------------------------
    def get_employee_full_name(self, obj):
        """Returns full name of the employee receiving the feedback."""
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"

    def validate_rating(self, value):
        if not (1 <= int(value) <= 10):
            raise serializers.ValidationError("Rating must be between 1 and 10.")
        return value

    def create(self, validated_data):
        """Automatically set created_by as logged-in user."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


# ======================================================
# General Feedback
# ======================================================
class GeneralFeedbackSerializer(BaseFeedbackSerializer):
    """Serializer for GeneralFeedback model."""
    class Meta(BaseFeedbackSerializer.Meta):
        model = GeneralFeedback


# ======================================================
# Manager Feedback
# ======================================================
class ManagerFeedbackSerializer(BaseFeedbackSerializer):
    """Serializer for ManagerFeedback model."""
    manager_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ManagerFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["manager_full_name"]

    def get_manager_full_name(self, obj):
        """Returns the full name of the manager providing feedback."""
        if obj.employee and obj.employee.manager and obj.employee.manager.user:
            m = obj.employee.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return "-"


# ======================================================
# Client Feedback
# ======================================================
class ClientFeedbackSerializer(BaseFeedbackSerializer):
    """Serializer for ClientFeedback model."""
    client_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    client_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ClientFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["client_name", "client_full_name"]

    def get_client_full_name(self, obj):
        """Returns client name in full_name format (if available)."""
        return obj.client_name.strip() if getattr(obj, "client_name", None) else "-"
