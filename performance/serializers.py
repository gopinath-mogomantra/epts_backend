# ===========================================================
# performance/serializers.py (PRODUCTION-READY VERSION)
# ===========================================================
from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import PerformanceEvaluation
from employee.models import Department, Employee
import logging

User = get_user_model()
logger = logging.getLogger("performance")


# ===========================================================
# UTILITY FUNCTIONS
# ===========================================================
def get_score_category(average_score):
    """
    Centralized score categorization logic.
    Returns performance category based on average score percentage.
    """
    if average_score >= 90:
        return "Excellent"
    elif average_score >= 80:
        return "Good"
    elif average_score >= 70:
        return "Average"
    elif average_score >= 60:
        return "Below Average"
    else:
        return "Poor"


# ===========================================================
# SIMPLE / RELATED SERIALIZERS (Optimized)
# ===========================================================
class SimpleUserSerializer(serializers.ModelSerializer):
    """Lightweight user serializer with full name."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        """Get full name with fallback."""
        try:
            name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
            return name or obj.username
        except (AttributeError, TypeError):
            return "Unknown"


class SimpleDepartmentSerializer(serializers.ModelSerializer):
    """Lightweight department serializer."""
    
    class Meta:
        model = Department
        fields = ["id", "name", "code"]


class SimpleEmployeeSerializer(serializers.ModelSerializer):
    """
    Lightweight employee serializer with related data.
    IMPORTANT: Views must use select_related('user', 'department', 'manager__user')
    """
    user = SimpleUserSerializer(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)
    manager_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "user", "designation", "status", "role",
            "department_name", "full_name", "manager_name",
        ]

    def get_full_name(self, obj):
        """Get full name with safe FK access (no extra query if prefetched)."""
        try:
            return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
        except (AttributeError, TypeError):
            return "Unknown"

    def get_manager_name(self, obj):
        """Get manager name with safe FK access (no extra query if prefetched)."""
        try:
            # Check manager_id first to avoid query
            if not obj.manager_id:
                return "-"
            
            # Access via prefetched data
            if hasattr(obj, 'manager') and obj.manager and hasattr(obj.manager, 'user'):
                mgr = obj.manager.user
                return f"{mgr.first_name} {mgr.last_name}".strip() or mgr.username
            return "-"
        except (AttributeError, TypeError):
            return "-"


# ===========================================================
# READ-ONLY SERIALIZER (List / Detail)
# ===========================================================
class PerformanceEvaluationSerializer(serializers.ModelSerializer):
    """
    Comprehensive read-only serializer for performance evaluations.
    Includes computed fields and nested relationships.
    """
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
        """
        Frontend-ready metrics dictionary for charts and visualizations.
        Returns all 15 evaluation metrics.
        """
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
        """Human-readable score display."""
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"

    def get_week_label(self, obj):
        """Week and year label for display."""
        return f"Week {obj.week_number}, {obj.year}"

    def get_score_category(self, obj):
        """Performance category based on score."""
        return get_score_category(obj.average_score)

    def to_representation(self, instance):
        """
        Add computed fields to response with safe FK access.
        Assumes select_related('employee__user', 'department') in view.
        """
        rep = super().to_representation(instance)
        
        # Safe department name access
        if instance.department_id and hasattr(instance, 'department'):
            rep["department_name"] = instance.department.name
        else:
            rep["department_name"] = None
        
        # Safe employee name access
        try:
            if instance.employee and hasattr(instance.employee, 'user'):
                user = instance.employee.user
                rep["employee_name"] = f"{user.first_name} {user.last_name}".strip() or user.username
            else:
                rep["employee_name"] = None
        except (AttributeError, TypeError):
            rep["employee_name"] = None
        
        return rep


# ===========================================================
# CREATE / UPDATE SERIALIZER (Fixed & Optimized)
# ===========================================================
class PerformanceCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating performance evaluations.
    Handles flexible employee ID input and comprehensive validation.
    """
    # Accept both 'employee' and 'employee_emp_id' inputs
    employee = serializers.CharField(write_only=True, required=False)
    employee_emp_id = serializers.CharField(write_only=True, required=False)
    evaluator_emp_id = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    department_code = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    # Define metric fields for validation
    METRIC_FIELDS = [
        'communication_skills', 'multitasking', 'team_skills',
        'technical_skills', 'job_knowledge', 'productivity',
        'creativity', 'work_quality', 'professionalism',
        'work_consistency', 'attitude', 'cooperation',
        'dependability', 'attendance', 'punctuality'
    ]

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

    # ---------------------- Validation ----------------------
    @transaction.atomic
    def validate(self, attrs):
        """
        Comprehensive validation with proper ordering and atomicity.
        Order: Permissions → Employee → Evaluator → Department → Duplicates → Metrics
        """
        
        # 1. CHECK PERMISSIONS FIRST
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            if request.user.role not in ["Admin", "Manager"]:
                raise serializers.ValidationError({
                    "permission": "Only Admin or Manager can submit evaluations."
                })
        
        # 2. VALIDATE EMPLOYEE
        emp_value = attrs.get("employee") or attrs.get("employee_emp_id")
        if not emp_value:
            raise serializers.ValidationError({
                "employee": "Employee ID is required."
            })

        try:
            emp = Employee.objects.select_related("user", "department").get(
                user__emp_id__iexact=emp_value
            )
        except Employee.DoesNotExist:
            raise serializers.ValidationError({
                "employee": f"Employee with emp_id '{emp_value}' not found."
            })

        # Validate employee status
        if emp.is_deleted:
            raise serializers.ValidationError({
                "employee": f"Employee {emp_value} is deleted and cannot be evaluated."
            })

        if emp.status != "Active":
            raise serializers.ValidationError({
                "employee": f"Employee {emp_value} is {emp.status} and cannot be evaluated."
            })

        if not emp.user.is_active:
            raise serializers.ValidationError({
                "employee": f"Employee {emp_value}'s user account is inactive."
            })

        self.context["employee"] = emp

        # 3. VALIDATE EVALUATOR
        evaluator_value = attrs.get("evaluator_emp_id")
        if evaluator_value:
            try:
                evaluator = User.objects.get(emp_id__iexact=evaluator_value)
            except User.DoesNotExist:
                raise serializers.ValidationError({
                    "evaluator_emp_id": f"Evaluator '{evaluator_value}' not found."
                })
            
            # Validate evaluator role
            if evaluator.role not in ["Admin", "Manager"]:
                raise serializers.ValidationError({
                    "evaluator_emp_id": "Evaluator must be Admin or Manager."
                })
            
            self.context["evaluator"] = evaluator
        else:
            # Default to current user
            if request and hasattr(request, "user"):
                self.context["evaluator"] = request.user
            else:
                raise serializers.ValidationError({
                    "evaluator_emp_id": "Evaluator is required."
                })

        # 4. VALIDATE DEPARTMENT
        dept_code = attrs.get("department_code")
        if dept_code:
            try:
                dept = Department.objects.get(code__iexact=dept_code, is_active=True)
            except Department.DoesNotExist:
                raise serializers.ValidationError({
                    "department_code": f"Department '{dept_code}' not found or inactive."
                })
            self.context["department"] = dept
        else:
            # Default to employee's department
            if not emp.department:
                raise serializers.ValidationError({
                    "department": "Employee has no department assigned."
                })
            self.context["department"] = emp.department

        # 5. CHECK FOR DUPLICATES (with locking)
        review_date = attrs.get("review_date", timezone.now().date())
        evaluation_type = attrs.get("evaluation_type", "Manager")

        week_number = review_date.isocalendar()[1]
        year = review_date.year

        # Lock employee's evaluations for this period
        existing_query = PerformanceEvaluation.objects.select_for_update().filter(
            employee=emp,
            week_number=week_number,
            year=year,
            evaluation_type=evaluation_type
        )

        if self.instance:
            existing_query = existing_query.exclude(pk=self.instance.pk)

        if existing_query.exists():
            raise serializers.ValidationError({
                "duplicate": f"Evaluation already exists for {emp.user.emp_id} "
                            f"(Week {week_number}, {year}, {evaluation_type})."
            })

        # Store for use in create()
        attrs['_week_number'] = week_number
        attrs['_year'] = year

        # 6. VALIDATE ALL METRICS
        errors = {}
        for field in self.METRIC_FIELDS:
            if field in attrs:
                value = attrs[field]
                try:
                    num = int(value)
                    if not (0 <= num <= 100):
                        errors[field] = "Metric must be between 0 and 100."
                except (TypeError, ValueError):
                    errors[field] = "Metric must be a valid integer."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    # ---------------------- Create ----------------------
    @transaction.atomic
    def create(self, validated_data):
        """Create performance evaluation with atomic transaction."""
        emp = self.context.get("employee")
        evaluator = self.context.get("evaluator")
        department = self.context.get("department")

        # Remove write-only fields
        for f in ["employee", "employee_emp_id", "evaluator_emp_id", "department_code", "_week_number", "_year"]:
            validated_data.pop(f, None)

        # Create evaluation
        instance = PerformanceEvaluation.objects.create(
            employee=emp,
            evaluator=evaluator,
            department=department,
            **validated_data,
        )

        # Trigger ranking calculation
        try:
            instance.auto_rank_trigger()
        except Exception as e:
            logger.error(
                f"Failed to auto-rank after creating evaluation: {e}",
                extra={
                    'evaluation_id': instance.id,
                    'employee': emp.emp_id
                },
                exc_info=True
            )
            # Don't fail creation, but log the error

        logger.info(
            f"Performance evaluation created",
            extra={
                'evaluation_id': instance.id,
                'employee': emp.emp_id,
                'evaluator': evaluator.emp_id,
                'week': instance.week_number,
                'year': instance.year
            }
        )

        return instance

    # ---------------------- Update ----------------------
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update performance evaluation with atomic transaction."""
        # Remove write-only fields
        for f in ["employee", "employee_emp_id", "evaluator_emp_id", "department_code", "_week_number", "_year"]:
            validated_data.pop(f, None)

        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Recalculate ranking
        try:
            instance.auto_rank_trigger()
        except Exception as e:
            logger.error(
                f"Failed to auto-rank after updating evaluation: {e}",
                extra={'evaluation_id': instance.id},
                exc_info=True
            )

        logger.info(
            f"Performance evaluation updated",
            extra={
                'evaluation_id': instance.id,
                'employee': instance.employee.emp_id
            }
        )

        return instance


# ===========================================================
# DASHBOARD / RANKING SERIALIZERS (Optimized)
# ===========================================================
class PerformanceDashboardSerializer(serializers.ModelSerializer):
    """
    Dashboard serializer with essential evaluation data.
    Use with select_related('employee__user', 'employee__manager__user', 'department')
    """
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
        """Get employee name with safe FK access."""
        try:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip() or u.username
        except (AttributeError, TypeError):
            return "Unknown"

    def get_manager_name(self, obj):
        """Get manager name with safe FK access."""
        try:
            if obj.employee.manager and obj.employee.manager.user:
                m = obj.employee.manager.user
                return f"{m.first_name} {m.last_name}".strip() or m.username
            return "-"
        except (AttributeError, TypeError):
            return "-"

    def get_score_display(self, obj):
        """Human-readable score display."""
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"

    def get_score_category(self, obj):
        """Performance category based on score."""
        return get_score_category(obj.average_score)


class PerformanceRankSerializer(serializers.ModelSerializer):
    """
    Ranking serializer for leaderboards and comparisons.
    Use with select_related('employee__user', 'department')
    """
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
        """Get employee full name with safe FK access."""
        try:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip() or u.username
        except (AttributeError, TypeError):
            return "Unknown"

    def get_score_display(self, obj):
        """Human-readable score display."""
        return f"{obj.total_score} / 1500 ({obj.average_score}%)"

    def get_score_category(self, obj):
        """Performance category based on score."""
        return get_score_category(obj.average_score)