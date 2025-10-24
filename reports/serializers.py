# ===============================================
# reports/serializers.py (Final Production Version)
# ===============================================
# Combines data from Performance + Feedback modules
# to generate weekly, monthly, manager-wise,
# department-wise, and employee history reports.
# ===============================================

from rest_framework import serializers
from performance.models import PerformanceEvaluation
from feedback.models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee
from .models import CachedReport


# -------------------------------------------------
# ✅ 1. Basic Employee Serializer
# -------------------------------------------------
class SimpleEmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)
    emp_id = serializers.CharField(source="user.emp_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "emp_id", "full_name", "email", "department_name"]

    def get_full_name(self, obj):
        user = getattr(obj, "user", None)
        if user:
            return f"{user.first_name or ''} {user.last_name or ''}".strip()
        return "-"


# -------------------------------------------------
# ✅ 2. Weekly Report Serializer
# -------------------------------------------------
class WeeklyReportSerializer(serializers.Serializer):
    """Represents a consolidated weekly report entry per employee."""
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField()
    remarks = serializers.CharField(allow_blank=True, allow_null=True, required=False)


# -------------------------------------------------
# ✅ 3. Monthly Report Serializer
# -------------------------------------------------
class MonthlyReportSerializer(serializers.Serializer):
    """Aggregated monthly summary of performance and feedback."""
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    avg_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    best_week = serializers.IntegerField()
    best_week_score = serializers.FloatField()


# -------------------------------------------------
# ✅ 4. Employee Performance History Serializer
# -------------------------------------------------
class EmployeeHistorySerializer(serializers.Serializer):
    """Weekly trend/history for a single employee."""
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    remarks = serializers.CharField(allow_null=True)
    rank = serializers.IntegerField(allow_null=True)


# -------------------------------------------------
# ✅ 5. Manager-Wise Report Serializer
# -------------------------------------------------
class ManagerReportSerializer(serializers.Serializer):
    """Weekly performance report of all employees under a manager."""
    manager_full_name = serializers.CharField()
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField()
    remarks = serializers.CharField(allow_blank=True, allow_null=True)


# -------------------------------------------------
# ✅ 6. Department-Wise Report Serializer
# -------------------------------------------------
class DepartmentReportSerializer(serializers.Serializer):
    """Weekly performance report of all employees in a department."""
    department_name = serializers.CharField()
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    manager_full_name = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField()
    remarks = serializers.CharField(allow_blank=True, allow_null=True)


# -------------------------------------------------
# ✅ 7. Cached Report Serializer
# -------------------------------------------------
class CachedReportSerializer(serializers.ModelSerializer):
    """Serializer for cached precomputed reports."""
    generated_by_full_name = serializers.SerializerMethodField(read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.username", read_only=True)
    period_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CachedReport
        fields = [
            "id",
            "report_type",
            "year",
            "week_number",
            "month",
            "manager",
            "department",
            "payload",
            "file_path",
            "generated_at",
            "generated_by",
            "generated_by_name",
            "generated_by_full_name",
            "is_active",
            "period_display",
        ]
        read_only_fields = [
            "id",
            "generated_at",
            "generated_by_name",
            "generated_by_full_name",
            "period_display",
        ]

    def get_generated_by_full_name(self, obj):
        user = getattr(obj, "generated_by", None)
        if user:
            return f"{user.first_name or ''} {user.last_name or ''}".strip()
        return "-"

    def get_period_display(self, obj):
        """Human-readable period label."""
        if obj.report_type in ["weekly", "manager", "department"] and obj.week_number:
            return f"Week {obj.week_number}, {obj.year}"
        if obj.report_type == "monthly" and obj.month:
            return f"Month {obj.month}, {obj.year}"
        return str(obj.year)


# -------------------------------------------------
# ✅ 8. Aggregated Report Helper Serializer
# -------------------------------------------------
class CombinedReportSerializer(serializers.Serializer):
    """Combines performance and feedback stats into one payload."""
    type = serializers.ChoiceField(
        choices=["weekly", "monthly", "manager", "department"]
    )
    year = serializers.IntegerField()
    week_or_month = serializers.IntegerField()
    generated_by_full_name = serializers.CharField()
    total_employees = serializers.IntegerField()
    average_org_score = serializers.FloatField()
    top_performers = serializers.ListField(child=serializers.CharField())
    weak_performers = serializers.ListField(child=serializers.CharField())
    feedback_summary = serializers.DictField(child=serializers.FloatField())

    def validate(self, data):
        """Ensure correct numeric bounds for period."""
        report_type = data.get("type")
        period = data.get("week_or_month")

        if report_type in ["weekly", "manager", "department"] and not (1 <= period <= 53):
            raise serializers.ValidationError("Invalid week number (1–53).")
        if report_type == "monthly" and not (1 <= period <= 12):
            raise serializers.ValidationError("Invalid month (1–12).")
        return data
