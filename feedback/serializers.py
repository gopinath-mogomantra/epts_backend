# feedback/serializers.py
from rest_framework import serializers
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee, Department
from django.contrib.auth import get_user_model

User = get_user_model()


class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "emp_id", "username", "first_name", "last_name", "full_name"]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


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
    employee_name = serializers.CharField(source="employee.user.username", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)

    class Meta:
        model = None  # defined in subclass
        fields = [
            "id",
            "employee",
            "employee_name",
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


class GeneralFeedbackSerializer(BaseFeedbackSerializer):
    """Serializer for GeneralFeedback model."""
    class Meta(BaseFeedbackSerializer.Meta):
        model = GeneralFeedback


class ManagerFeedbackSerializer(BaseFeedbackSerializer):
    """Serializer for ManagerFeedback model."""
    manager_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ManagerFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["manager_name"]


class ClientFeedbackSerializer(BaseFeedbackSerializer):
    """Serializer for ClientFeedback model."""
    client_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    class Meta(BaseFeedbackSerializer.Meta):
        model = ClientFeedback
        fields = BaseFeedbackSerializer.Meta.fields + ["client_name"]
