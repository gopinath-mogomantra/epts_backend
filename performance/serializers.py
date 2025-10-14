# ===============================================
# performance/serializers.py
# ===============================================
# Serializers for Performance Evaluation CRUD,
# dashboard views, and reporting.
# ===============================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PerformanceEvaluation
from employee.models import Department, Employee

User = get_user_model()


# ======================================================
# ✅ 1. Nested / Related Serializers
# ======================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    """Minimal representation of a user (for evaluator info)."""

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "email"]


class SimpleDepartmentSerializer(serializers.ModelSerializer):
    """Minimal representation of department."""

    class Meta:
        model = Department
        fields = ["id", "name"]


class SimpleEmployeeSerializer(serializers.ModelSerializer):
    """Employee info (linked to CustomUser)."""
    user = SimpleUserSerializer(read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "user", "designation", "status", "role"]

    def get_role(self, obj):
        """Fetch user.role from linked User model."""
        return obj.user.role if obj.user else None


# ======================================================
# ✅ 2. Full Performance Evaluation Serializer (GET)
# ======================================================
class PerformanceEvaluationSerializer(serializers.ModelSerializer):
    """
    Used for retrieving performance evaluations (Admin/Manager views).
    """
    employee = SimpleEmployeeSerializer(read_only=True)
    evaluator = SimpleUserSerializer(read_only=True)
    department = SimpleDepartmentSerializer(read_only=True)
    evaluation_summary = serializers.SerializerMethodField()
    score_display = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id",
            "employee",
            "evaluator",
            "department",
            "evaluation_type",
            "review_date",
            "evaluation_period",
            "week_number",
            "year",
            "evaluation_summary",
            "total_score",
            "score_display",
            "remarks",
            "created_at",
            "updated_at",
        ]

    def get_evaluation_summary(self, obj):
        """Return detailed metric scores for frontend display."""
        metrics = [
            ("Communication Skills", obj.communication_skills),
            ("Multitasking", obj.multitasking),
            ("Team Skills", obj.team_skills),
            ("Technical Skills", obj.technical_skills),
            ("Job Knowledge", obj.job_knowledge),
            ("Productivity", obj.productivity),
            ("Creativity", obj.creativity),
            ("Work Quality", obj.work_quality),
            ("Professionalism", obj.professionalism),
            ("Work Consistency", obj.work_consistency),
            ("Attitude", obj.attitude),
            ("Cooperation", obj.cooperation),
            ("Dependability", obj.dependability),
            ("Attendance", obj.attendance),
            ("Punctuality", obj.punctuality),
        ]
        return [{"metric": name, "score": score} for name, score in metrics]

    def get_score_display(self, obj):
        """Readable score format."""
        return f"{obj.total_score} / 1500"


# ======================================================
# ✅ 3. Create/Update Serializer (POST/PUT)
# ======================================================
class PerformanceCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Used by Admin/Manager/Client to create or update performance records.
    Automatically recalculates total score.
    """
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    evaluator = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id",
            "employee",
            "evaluator",
            "department",
            "evaluation_type",
            "review_date",
            "evaluation_period",
            "communication_skills",
            "multitasking",
            "team_skills",
            "technical_skills",
            "job_knowledge",
            "productivity",
            "creativity",
            "work_quality",
            "professionalism",
            "work_consistency",
            "attitude",
            "cooperation",
            "dependability",
            "attendance",
            "punctuality",
            "remarks",
        ]

    def validate(self, data):
        """Ensures each metric score is between 0–100."""
        metric_fields = [
            "communication_skills", "multitasking", "team_skills",
            "technical_skills", "job_knowledge", "productivity",
            "creativity", "work_quality", "professionalism",
            "work_consistency", "attitude", "cooperation",
            "dependability", "attendance", "punctuality",
        ]
        for field in metric_fields:
            value = data.get(field, 0)
            if not (0 <= int(value) <= 100):
                raise serializers.ValidationError({field: "Score must be between 0 and 100."})
        return data

    def create(self, validated_data):
        """Auto-calculates total_score before saving."""
        instance = PerformanceEvaluation.objects.create(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        """Recalculate total_score when updating."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ======================================================
# ✅ 4. Employee Dashboard Serializer (For Self View)
# ======================================================
class PerformanceDashboardSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for employee self-dashboard.
    """
    emp_id = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    score_display = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id",
            "emp_id",
            "employee_name",
            "review_date",
            "evaluation_period",
            "evaluation_type",
            "total_score",
            "score_display",
            "remarks",
        ]

    def get_emp_id(self, obj):
        return getattr(obj.employee.user, "emp_id", None)

    def get_employee_name(self, obj):
        user = obj.employee.user
        return f"{user.first_name} {user.last_name}".strip()

    def get_score_display(self, obj):
        return f"{obj.total_score} / 1500"
