# ===============================================
# performance/serializers.py (Final Polished Version)
# ===============================================

from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import PerformanceEvaluation
from employee.models import Department, Employee

User = get_user_model()


# ======================================================
# ✅ 1. Nested / Related Serializers
# ======================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "full_name", "email"]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()


class SimpleDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name"]


class SimpleEmployeeSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "user", "designation", "status", "role", "manager_name", "department_name"]

    def get_role(self, obj):
        return obj.user.role if obj.user else None

    def get_manager_name(self, obj):
        if obj.manager and obj.manager.user:
            m = obj.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return None


# ======================================================
# ✅ 2. Full Performance Evaluation Serializer (GET)
# ======================================================
class PerformanceEvaluationSerializer(serializers.ModelSerializer):
    employee = SimpleEmployeeSerializer(read_only=True)
    evaluator = SimpleUserSerializer(read_only=True)
    department = SimpleDepartmentSerializer(read_only=True)
    evaluation_summary = serializers.SerializerMethodField()
    score_display = serializers.SerializerMethodField()
    week_label = serializers.SerializerMethodField()

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
            "week_label",
            "evaluation_summary",
            "total_score",
            "average_score",
            "rank",
            "score_display",
            "remarks",
            "created_at",
            "updated_at",
        ]

    def get_evaluation_summary(self, obj):
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
        return [{"metric": n, "score": s} for n, s in metrics]

    def get_score_display(self, obj):
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"

    def get_week_label(self, obj):
        return f"Week {obj.week_number}, {obj.year}"


# ======================================================
# ✅ 3. Create / Update Serializer (POST / PUT)
# ======================================================
class PerformanceCreateUpdateSerializer(serializers.ModelSerializer):
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
        emp = validated_data["employee"]
        week = validated_data.get("week_number") or timezone.now().isocalendar()[1]
        year = validated_data.get("year") or timezone.now().year
        if PerformanceEvaluation.objects.filter(
            employee=emp, week_number=week, year=year, evaluation_type=validated_data.get("evaluation_type")
        ).exists():
            raise serializers.ValidationError("Performance for this week and evaluator type already exists.")
        instance = PerformanceEvaluation.objects.create(**validated_data)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ======================================================
# ✅ 4. Dashboard / Summary Serializer
# ======================================================
class PerformanceDashboardSerializer(serializers.ModelSerializer):
    emp_id = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    score_display = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id",
            "emp_id",
            "employee_name",
            "manager_name",
            "department_name",
            "review_date",
            "evaluation_period",
            "evaluation_type",
            "total_score",
            "average_score",
            "rank",
            "score_display",
            "remarks",
        ]

    def get_emp_id(self, obj):
        return getattr(obj.employee.user, "emp_id", None)

    def get_employee_name(self, obj):
        u = obj.employee.user
        return f"{u.first_name} {u.last_name}".strip()

    def get_manager_name(self, obj):
        if obj.employee.manager and obj.employee.manager.user:
            m = obj.employee.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return "-"

    def get_score_display(self, obj):
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"
