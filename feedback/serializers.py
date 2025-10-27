from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee, Department

User = get_user_model()


# ===========================================================
# ✅ Simple User Serializer (Reusable)
# ===========================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "emp_id", "username", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


# ===========================================================
# ✅ Base Feedback Serializer (Shared Logic)
# ===========================================================
class BaseFeedbackSerializer(serializers.ModelSerializer):
    """
    Base serializer for all feedback types.
    Provides validation, department consistency, and created_by auto-linking.
    """

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    created_by = SimpleUserSerializer(read_only=True)

    # Derived / Computed fields
    employee_full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    visibility_label = serializers.CharField(source="get_visibility_display", read_only=True)

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
            "visibility_label",
            "created_by",
            "feedback_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    # -------------------------------------------------------
    # Derived field helpers
    # -------------------------------------------------------
    def get_employee_full_name(self, obj):
        """Return the employee’s full name."""
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"

    # -------------------------------------------------------
    # Validation
    # -------------------------------------------------------
    def validate_rating(self, value):
        """Ensure rating between 1 and 10."""
        if not (1 <= int(value) <= 10):
            raise serializers.ValidationError("Rating must be between 1 and 10.")
        return value

    def validate(self, attrs):
        """Ensure department matches the employee’s actual department."""
        employee = attrs.get("employee")
        department = attrs.get("department")

        if employee:
            # Auto-fill department if missing
            if not department:
                attrs["department"] = employee.department
            elif employee.department and department != employee.department:
                raise serializers.ValidationError(
                    {"department": "Department does not match the employee’s assigned department."}
                )
        return attrs

    # -------------------------------------------------------
    # Creation
    # -------------------------------------------------------
    def create(self, validated_data):
        """Automatically attach created_by and auto-fill missing fields."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        instance = super().create(validated_data)
        return instance

    # -------------------------------------------------------
    # Dashboard Summary Helper
    # -------------------------------------------------------
    def to_representation(self, instance):
        """Return consistent data for UI and analytics."""
        rep = super().to_representation(instance)
        rep["feedback_date"] = instance.feedback_date.isoformat()
        rep["rating_display"] = f"{instance.rating}/10"
        return rep


# ===========================================================
# ✅ General Feedback Serializer
# ===========================================================
class GeneralFeedbackSerializer(BaseFeedbackSerializer):
    """Handles General Feedback — given by Admin or HR."""

    class Meta(BaseFeedbackSerializer.Meta):
        model = GeneralFeedback


# ===========================================================
# ✅ Manager Feedback Serializer
# ===========================================================
class ManagerFeedbackSerializer(BaseFeedbackSerializer):
    """Handles Manager Feedback — typically submitted by Managers."""
    manager_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ManagerFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["manager_full_name"]

    def get_manager_full_name(self, obj):
        """Return manager’s name associated with the employee."""
        if obj.employee and obj.employee.manager and obj.employee.manager.user:
            m = obj.employee.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return "-"

    def validate(self, attrs):
        """Managers can only submit feedback for their own team."""
        request = self.context.get("request")
        employee = attrs.get("employee")

        if request and hasattr(request.user, "role") and request.user.role == "Manager":
            try:
                manager_emp = Employee.objects.get(user=request.user)
                if employee.manager_id != manager_emp.id:
                    raise serializers.ValidationError({
                        "employee": "You can only submit feedback for your team members."
                    })
            except Employee.DoesNotExist:
                raise serializers.ValidationError({
                    "employee": "Manager record not found for current user."
                })
        return super().validate(attrs)


# ===========================================================
# ✅ Client Feedback Serializer
# ===========================================================
class ClientFeedbackSerializer(BaseFeedbackSerializer):
    """Handles Client Feedback — provided by clients."""
    client_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    client_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ClientFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["client_name", "client_full_name"]

    def get_client_full_name(self, obj):
        """Return formatted client name or fallback."""
        return (obj.client_name or "Anonymous Client").strip()

    def create(self, validated_data):
        """Auto-fill 'Anonymous Client' if no name provided."""
        if not validated_data.get("client_name"):
            validated_data["client_name"] = "Anonymous Client"
        return super().create(validated_data)
