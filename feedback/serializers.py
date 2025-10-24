# ===============================================
# feedback/serializers.py (Final Synced Version)
# ===============================================

from rest_framework import serializers
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee, Department
from django.contrib.auth import get_user_model

User = get_user_model()


# ======================================================
# ✅ Simple User Serializer (Reusable)
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
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


# ======================================================
# ✅ Base Feedback Serializer (Shared Logic)
# ======================================================
class BaseFeedbackSerializer(serializers.ModelSerializer):
    """
    Base serializer for all feedback types.
    Handles shared fields and automatic user association.
    """

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        required=False,
        allow_null=True
    )
    created_by = SimpleUserSerializer(read_only=True)

    # Derived fields
    employee_full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = None  # overridden in subclasses
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

    # ---------------------------------------------------
    # Field-level and object-level validation
    # ---------------------------------------------------
    def get_employee_full_name(self, obj):
        """Return employee's full name."""
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"

    def validate_rating(self, value):
        """Ensure rating between 1 and 10."""
        if not (1 <= int(value) <= 10):
            raise serializers.ValidationError("Rating must be between 1 and 10.")
        return value

    def validate(self, attrs):
        """Ensure department matches employee’s department."""
        employee = attrs.get("employee")
        department = attrs.get("department")

        if employee:
            # Auto-fill department if not given
            if not department:
                attrs["department"] = employee.department
            elif employee.department and department != employee.department:
                raise serializers.ValidationError({
                    "department": "Department does not match the employee’s assigned department."
                })
        return attrs

    def create(self, validated_data):
        """Automatically attach created_by user."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


# ======================================================
# ✅ General Feedback Serializer
# ======================================================
class GeneralFeedbackSerializer(BaseFeedbackSerializer):
    """Handles GeneralFeedback — given by Admin or HR."""
    class Meta(BaseFeedbackSerializer.Meta):
        model = GeneralFeedback


# ======================================================
# ✅ Manager Feedback Serializer
# ======================================================
class ManagerFeedbackSerializer(BaseFeedbackSerializer):
    """Handles ManagerFeedback — given by Managers."""
    manager_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ManagerFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["manager_full_name"]

    def get_manager_full_name(self, obj):
        """Return the manager’s full name for this employee."""
        if obj.employee and obj.employee.manager and obj.employee.manager.user:
            m = obj.employee.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return "-"


# ======================================================
# ✅ Client Feedback Serializer
# ======================================================
class ClientFeedbackSerializer(BaseFeedbackSerializer):
    """Handles ClientFeedback — feedback from clients."""
    client_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    client_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ClientFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["client_name", "client_full_name"]

    def get_client_full_name(self, obj):
        """Return formatted client name."""
        return (obj.client_name or "-").strip()
