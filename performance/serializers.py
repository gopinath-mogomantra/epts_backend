from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import PerformanceEvaluation
from employee.models import Department, Employee

User = get_user_model()


# ======================================================
# Nested / Related Serializers
# ======================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
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


class SimpleDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "code"]


class SimpleEmployeeSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)
    role = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()
    manager_full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "designation",
            "status",
            "role",
            "department_name",
            "full_name",
            "manager_name",
            "manager_full_name",
        ]

    def get_role(self, obj):
        return getattr(obj.user, "role", None)

    def get_full_name(self, obj):
        """Return employee full name from user."""
        first = obj.user.first_name or ""
        last = obj.user.last_name or ""
        return f"{first} {last}".strip()

    def get_manager_name(self, obj):
        """Short manager name (first only)."""
        if obj.manager and obj.manager.user:
            return obj.manager.user.first_name
        return None

    def get_manager_full_name(self, obj):
        """Full manager name (first + last)."""
        if obj.manager and obj.manager.user:
            m = obj.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return None


# ======================================================
# GET Serializer (Read-Only)
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
# CREATE / UPDATE Serializer (with emp_id + dept_code)
# ======================================================
class PerformanceCreateUpdateSerializer(serializers.ModelSerializer):
    employee_emp_id = serializers.CharField(write_only=True)
    evaluator_emp_id = serializers.CharField(write_only=True, required=False, allow_null=True)
    department_code = serializers.CharField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id",
            "employee_emp_id",
            "evaluator_emp_id",
            "department_code",
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

    # --------------------------------------------------
    # Validate Employee
    # --------------------------------------------------
    def validate_employee_emp_id(self, value):
        from employee.models import Employee
        try:
            emp = Employee.objects.select_related("user", "department").get(user__emp_id__iexact=value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError(f"Employee with emp_id '{value}' not found.")
        self.context["employee"] = emp
        return value

    # --------------------------------------------------
    # Validate Evaluator
    # --------------------------------------------------
    def validate_evaluator_emp_id(self, value):
        if not value:
            return None
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            evaluator = User.objects.get(emp_id__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Evaluator with emp_id '{value}' not found.")
        self.context["evaluator"] = evaluator
        return value

    # --------------------------------------------------
    # Validate Department
    # --------------------------------------------------
    def validate_department_code(self, value):
        if not value:
            return None
        from employee.models import Department
        try:
            dept = Department.objects.get(code__iexact=value, is_active=True)
        except Department.DoesNotExist:
            raise serializers.ValidationError(f"Department with code '{value}' not found or inactive.")
        self.context["department"] = dept
        return value

    # --------------------------------------------------
    # Global Validation
    # --------------------------------------------------
    def validate(self, attrs):
        employee = self.context.get("employee")
        review_date = attrs.get("review_date", timezone.now().date())
        evaluation_type = attrs.get("evaluation_type", "Manager")

        # Prevent duplicate evaluations for same week + evaluator
        week_number = review_date.isocalendar()[1]
        year = review_date.year
        existing = PerformanceEvaluation.objects.filter(
            employee=employee, week_number=week_number, year=year, evaluation_type=evaluation_type
        )
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                f"Performance evaluation already exists for {employee.user.emp_id} in Week {week_number}, {year} ({evaluation_type})."
            )

        # Only Admin or Manager can create evaluations
        request = self.context.get("request")
        if request and hasattr(request.user, "role"):
            role = request.user.role.lower()
            if role not in ["admin", "manager"]:
                raise serializers.ValidationError({"evaluator": "Only Admin or Manager can create evaluations."})
        return attrs

    # --------------------------------------------------
    # CREATE
    # --------------------------------------------------
    def create(self, validated_data):
        emp = self.context.get("employee")
        evaluator = self.context.get("evaluator", None)
        department = self.context.get("department", emp.department if emp else None)

        # Remove extra fields before saving
        validated_data.pop("employee_emp_id", None)
        validated_data.pop("evaluator_emp_id", None)
        validated_data.pop("department_code", None)

        evaluation = PerformanceEvaluation.objects.create(
            employee=emp,
            evaluator=evaluator,
            department=department,
            **validated_data,
        )
        return evaluation

    # --------------------------------------------------
    # UPDATE
    # --------------------------------------------------
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ======================================================
# DASHBOARD / SUMMARY Serializer
# ======================================================
class PerformanceDashboardSerializer(serializers.ModelSerializer):
    emp_id = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    employee_full_name = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()
    manager_full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    score_display = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id",
            "emp_id",
            "employee_name",
            "employee_full_name",
            "manager_name",
            "manager_full_name",
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
        """Short employee name (first name only)."""
        return obj.employee.user.first_name

    def get_employee_full_name(self, obj):
        """Full employee name (first + last)."""
        u = obj.employee.user
        return f"{u.first_name} {u.last_name}".strip()

    def get_manager_name(self, obj):
        """Short manager name (first name only)."""
        if obj.employee.manager and obj.employee.manager.user:
            return obj.employee.manager.user.first_name
        return "-"

    def get_manager_full_name(self, obj):
        """Full manager name (first + last)."""
        if obj.employee.manager and obj.employee.manager.user:
            m = obj.employee.manager.user
            return f"{m.first_name} {m.last_name}".strip()
        return "-"

    def get_score_display(self, obj):
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"
