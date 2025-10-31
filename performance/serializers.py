# ===========================================================
# performance/serializers.py 
# ===========================================================
from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import PerformanceEvaluation
from employee.models import Department, Employee

User = get_user_model()


# ===========================================================
# SIMPLE / RELATED SERIALIZERS
# ===========================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


class SimpleDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "code"]


class SimpleEmployeeSerializer(serializers.ModelSerializer):
    user = SimpleUserSerializer(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id", "user", "designation", "status", "role",
            "department_name", "full_name", "manager_name",
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def get_manager_name(self, obj):
        if obj.manager and obj.manager.user:
            mgr = obj.manager.user
            return f"{mgr.first_name} {mgr.last_name}".strip()
        return "-"


# ===========================================================
# READ-ONLY SERIALIZER (List / Detail)
# ===========================================================
class PerformanceEvaluationSerializer(serializers.ModelSerializer):
    employee = SimpleEmployeeSerializer(read_only=True)
    evaluator = SimpleUserSerializer(read_only=True)
    department = SimpleDepartmentSerializer(read_only=True)

    metrics = serializers.SerializerMethodField()
    score_display = serializers.SerializerMethodField()
    week_label = serializers.SerializerMethodField()
    score_category = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id", "employee", "evaluator", "department",
            "evaluation_type", "review_date", "evaluation_period",
            "week_number", "year", "week_label",
            "metrics", "total_score", "average_score",
            "rank", "score_display", "score_category",
            "remarks", "created_at", "updated_at",
        ]

    def get_metrics(self, obj):
        """Frontend-ready metrics for charts."""
        return {
            "communication": obj.communication_skills,
            "multitasking": obj.multitasking,
            "team_skills": obj.team_skills,
            "technical_skills": obj.technical_skills,
            "job_knowledge": obj.job_knowledge,
            "productivity": obj.productivity,
            "creativity": obj.creativity,
            "work_quality": obj.work_quality,
            "professionalism": obj.professionalism,
            "consistency": obj.work_consistency,
            "attitude": obj.attitude,
            "cooperation": obj.cooperation,
            "dependability": obj.dependability,
            "attendance": obj.attendance,
            "punctuality": obj.punctuality,
        }

    def get_score_display(self, obj):
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"

    def get_week_label(self, obj):
        return f"Week {obj.week_number}, {obj.year}"

    def get_score_category(self, obj):
        score = obj.average_score
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Average"
        elif score >= 60:
            return "Below Average"
        else:
            return "Poor"

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["department_name"] = getattr(instance.department, "name", None)
        rep["employee_name"] = (
            f"{instance.employee.user.first_name} {instance.employee.user.last_name}".strip()
            if instance.employee and instance.employee.user else None
        )
        return rep


# ===========================================================
# CREATE / UPDATE SERIALIZER (Fixed for "employee": "EMPxxxx" input)
# ===========================================================
class PerformanceCreateUpdateSerializer(serializers.ModelSerializer):
    # Accept both 'employee' and 'employee_emp_id' inputs
    employee = serializers.CharField(write_only=True, required=False)
    employee_emp_id = serializers.CharField(write_only=True, required=False)
    evaluator_emp_id = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    department_code = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id", "employee", "employee_emp_id", "evaluator_emp_id", "department_code",
            "evaluation_type", "review_date", "evaluation_period",
            "communication_skills", "multitasking", "team_skills",
            "technical_skills", "job_knowledge", "productivity", "creativity",
            "work_quality", "professionalism", "work_consistency",
            "attitude", "cooperation", "dependability", "attendance",
            "punctuality", "remarks",
        ]

    # ---------------------- Validations ----------------------
    def validate(self, attrs):
        # Accept employee via either "employee" or "employee_emp_id"
        emp_value = attrs.get("employee") or attrs.get("employee_emp_id")
        if not emp_value:
            raise serializers.ValidationError({"employee": "Employee ID is required."})

        try:
            emp = Employee.objects.select_related("user", "department").get(user__emp_id__iexact=emp_value)
        except Employee.DoesNotExist:
            raise serializers.ValidationError({"employee": f"Employee with emp_id '{emp_value}' not found."})
        self.context["employee"] = emp

        # Evaluator handling
        evaluator_value = attrs.get("evaluator_emp_id")
        if evaluator_value:
            try:
                evaluator = User.objects.get(emp_id__iexact=evaluator_value)
            except User.DoesNotExist:
                raise serializers.ValidationError({"evaluator_emp_id": f"Evaluator '{evaluator_value}' not found."})
            self.context["evaluator"] = evaluator
        else:
            request = self.context.get("request")
            if request and hasattr(request, "user"):
                self.context["evaluator"] = request.user

        # Department handling
        dept_code = attrs.get("department_code")
        if dept_code:
            try:
                dept = Department.objects.get(code__iexact=dept_code, is_active=True)
            except Department.DoesNotExist:
                raise serializers.ValidationError({"department_code": f"Department '{dept_code}' not found or inactive."})
            self.context["department"] = dept
        else:
            self.context["department"] = emp.department

        # Prevent duplicate evaluations for same week/year/type
        review_date = attrs.get("review_date", timezone.now().date())
        evaluation_type = attrs.get("evaluation_type", "Manager")

        week_number = review_date.isocalendar()[1]
        year = review_date.year

        existing = PerformanceEvaluation.objects.filter(
            employee=emp, week_number=week_number, year=year, evaluation_type=evaluation_type
        )
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError({
                "duplicate": f"Evaluation already exists for {emp.user.emp_id} (Week {week_number}, {year}, {evaluation_type})."
            })

        # Metric validation — ensure 0–100 integer values
        for field, value in attrs.items():
            if field.endswith("_skills") or field in [
                "job_knowledge", "productivity", "creativity",
                "work_quality", "professionalism", "work_consistency",
                "attitude", "cooperation", "dependability", "attendance", "punctuality"
            ]:
                try:
                    num = int(value)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({field: "Metric must be an integer between 0–100."})
                if not (0 <= num <= 100):
                    raise serializers.ValidationError({field: "Metric must be between 0–100."})

        # Role restriction: Only Admin or Manager can evaluate
        request = self.context.get("request")
        if request and hasattr(request.user, "role"):
            if request.user.role not in ["Admin", "Manager"]:
                raise serializers.ValidationError({"role": "Only Admin or Manager can submit evaluations."})

        return attrs

    # ---------------------- Create ----------------------
    def create(self, validated_data):
        emp = self.context.get("employee")
        evaluator = self.context.get("evaluator")
        department = self.context.get("department")

        for f in ["employee", "employee_emp_id", "evaluator_emp_id", "department_code"]:
            validated_data.pop(f, None)

        instance = PerformanceEvaluation.objects.create(
            employee=emp,
            evaluator=evaluator,
            department=department,
            **validated_data,
        )

        instance.auto_rank_trigger()
        return instance

    # ---------------------- Update ----------------------
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        instance.auto_rank_trigger()
        return instance


# ===========================================================
# DASHBOARD / RANKING SERIALIZERS
# ===========================================================
class PerformanceDashboardSerializer(serializers.ModelSerializer):
    emp_id = serializers.ReadOnlyField(source="employee.user.emp_id")
    employee_name = serializers.SerializerMethodField()
    manager_name = serializers.SerializerMethodField()
    department_name = serializers.ReadOnlyField(source="department.name")
    score_display = serializers.SerializerMethodField()
    score_category = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "id", "emp_id", "employee_name", "manager_name",
            "department_name", "review_date", "evaluation_period",
            "evaluation_type", "total_score", "average_score",
            "rank", "score_display", "score_category", "remarks",
        ]

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

    def get_score_category(self, obj):
        score = obj.average_score
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Average"
        elif score >= 60:
            return "Below Average"
        else:
            return "Poor"


class PerformanceRankSerializer(serializers.ModelSerializer):
    emp_id = serializers.ReadOnlyField(source="employee.user.emp_id")
    full_name = serializers.SerializerMethodField()
    department_name = serializers.ReadOnlyField(source="department.name")
    score_display = serializers.SerializerMethodField()
    score_category = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            "emp_id", "full_name", "department_name",
            "average_score", "rank", "score_display", "score_category"
        ]

    def get_full_name(self, obj):
        u = obj.employee.user
        return f"{u.first_name} {u.last_name}".strip()

    def get_score_display(self, obj):
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"

    def get_score_category(self, obj):
        score = obj.average_score
        if score >= 90:
            return "Excellent"
        elif score >= 80:
            return "Good"
        elif score >= 70:
            return "Average"
        elif score >= 60:
            return "Below Average"
        else:
            return "Poor"
