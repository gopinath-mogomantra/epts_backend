# ===============================================
# reports/serializers.py (Final — full_name standardized)
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
        u = obj.user
        first = u.first_name or ""
        last = u.last_name or ""
        return f"{first} {last}".strip()


# -------------------------------------------------
# ✅ 2. Weekly Report Serializer
# -------------------------------------------------
class WeeklyReportSerializer(serializers.Serializer):
    """Represents a consolidated weekly report entry per employee."""
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()  # ✅ updated name
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
    employee_full_name = serializers.CharField()  # ✅ updated
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
    manager_full_name = serializers.CharField()  # ✅ updated
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()  # ✅ updated
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
    employee_full_name = serializers.CharField()  # ✅ updated
    manager_full_name = serializers.CharField()   # ✅ updated
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
    generated_by_full_name = serializers.SerializerMethodField(read_only=True)  # ✅ added
    generated_by_name = serializers.CharField(source="generated_by.username", read_only=True)
    period_display = serializers.SerializerMethodField()

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
            "generated_by_full_name",  # ✅ added
            "is_active",
            "period_display",
        ]
        read_only_fields = ["generated_at", "generated_by_name", "generated_by_full_name", "period_display"]

    def get_generated_by_full_name(self, obj):
        """Return the full name of the report generator."""
        if obj.generated_by:
            first = obj.generated_by.first_name or ""
            last = obj.generated_by.last_name or ""
            return f"{first} {last}".strip()
        return "-"

    def get_period_display(self, obj):
        """Readable label for report period."""
        if obj.report_type in ["weekly", "manager", "department"] and obj.week_number:
            return f"Week {obj.week_number}, {obj.year}"
        elif obj.report_type == "monthly" and obj.month:
            return f"Month {obj.month}, {obj.year}"
        return str(obj.year)


# -------------------------------------------------
# ✅ 8. Aggregated Report Helper Serializer
# -------------------------------------------------
class CombinedReportSerializer(serializers.Serializer):
    """Combines performance and feedback stats into one payload."""
    type = serializers.ChoiceField(choices=["weekly", "monthly", "manager", "department"])
    year = serializers.IntegerField()
    week_or_month = serializers.IntegerField()
    generated_by_full_name = serializers.CharField()  # ✅ added
    total_employees = serializers.IntegerField()
    average_org_score = serializers.FloatField()
    top_performers = serializers.ListField(child=serializers.CharField())
    weak_performers = serializers.ListField(child=serializers.CharField())
    feedback_summary = serializers.DictField(child=serializers.FloatField())

    def validate(self, data):
        """Ensure week_or_month is valid for report type."""
        if data["type"] in ["weekly", "manager", "department"] and not (1 <= data["week_or_month"] <= 53):
            raise serializers.ValidationError("Invalid week number (1–53).")
        if data["type"] == "monthly" and not (1 <= data["week_or_month"] <= 12):
            raise serializers.ValidationError("Invalid month (1–12).")
        return data
