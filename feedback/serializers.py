# ===========================================================
# feedback/serializers.py
# ===========================================================
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee, Department

User = get_user_model()


# ===========================================================
# Simple User Serializer (Reusable)
# ===========================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "emp_id", "username", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


# ===========================================================
# Base Feedback Serializer (Shared Logic)
# ===========================================================
class BaseFeedbackSerializer(serializers.ModelSerializer):
    """
    Shared serializer for all feedback types.
    Includes validation, consistency, and UI formatting.
    """

    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    created_by = SimpleUserSerializer(read_only=True)

    # Derived / Computed fields
    employee_full_name = serializers.SerializerMethodField(read_only=True)
    emp_id = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    visibility_label = serializers.CharField(source="get_visibility_display", read_only=True)
    source_type = serializers.CharField(read_only=True)
    rating_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = None 
        fields = [
            "id",
            "employee",
            "emp_id",
            "employee_full_name",
            "department",
            "department_name",
            "feedback_text",
            "remarks",
            "rating",
            "rating_display",
            "visibility",
            "visibility_label",
            "created_by",
            "source_type",
            "feedback_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at", "source_type"]

    # -------------------------------------------------------
    # Derived field helpers
    # -------------------------------------------------------
    def get_employee_full_name(self, obj):
        """Return the employee’s full name."""
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"

    def get_emp_id(self, obj):
        """Return employee emp_id."""
        if obj.employee and obj.employee.user:
            return obj.employee.user.emp_id
        return None

    def get_rating_display(self, obj):
        """Return formatted rating string."""
        return f"{obj.rating}/10"

    # -------------------------------------------------------
    # Validation
    # -------------------------------------------------------
    def validate_rating(self, value):
        if not (1 <= int(value) <= 10):
            raise serializers.ValidationError("Rating must be between 1 and 10.")
        return value

    def validate(self, attrs):
        """Ensure department matches the employee’s actual department."""
        employee = attrs.get("employee")
        department = attrs.get("department")

        if employee:
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
        """Attach created_by and fill missing department."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        instance = super().create(validated_data)
        return instance

    # -------------------------------------------------------
    # UI Representation
    # -------------------------------------------------------
    def to_representation(self, instance):
        """Return consistent format for dashboards and reports."""
        rep = super().to_representation(instance)
        rep["feedback_date"] = instance.feedback_date.strftime("%Y-%m-%d")
        rep["submitted_by"] = (
            f"{instance.created_by.first_name} {instance.created_by.last_name}".strip()
            if instance.created_by else "-"
        )
        rep["department_name"] = getattr(instance.department, "name", "-")
        rep["employee_name"] = self.get_employee_full_name(instance)
        return rep


# ===========================================================
# General Feedback Serializer
# ===========================================================
class GeneralFeedbackSerializer(BaseFeedbackSerializer):
    """General feedback from Admins or HR."""

    class Meta(BaseFeedbackSerializer.Meta):
        model = GeneralFeedback


# ===========================================================
# Manager Feedback Serializer
# ===========================================================
class ManagerFeedbackSerializer(BaseFeedbackSerializer):
    """Manager feedback for employees."""

    manager_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ManagerFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["manager_full_name"]

    def get_manager_full_name(self, obj):
        """Return manager’s name assigned to employee."""
        if obj.employee and obj.employee.manager and obj.employee.manager.user:
            m = obj.employee.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return "-"

    def validate(self, attrs):
        """Managers can only submit feedback for their team members."""
        request = self.context.get("request")
        employee = attrs.get("employee")

        if request and getattr(request.user, "role", "") == "Manager":
            try:
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


# ===========================================================
# Client Feedback Serializer
# ===========================================================
class ClientFeedbackSerializer(BaseFeedbackSerializer):
    """Feedback from clients on employees or projects."""

    client_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    client_full_name = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ClientFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["client_name", "client_full_name"]

    def get_client_full_name(self, obj):
        """Return client’s name or 'Anonymous Client'."""
        return (obj.client_name or "Anonymous Client").strip()

    def create(self, validated_data):
        if not validated_data.get("client_name"):
            validated_data["client_name"] = "Anonymous Client"
        return super().create(validated_data)
