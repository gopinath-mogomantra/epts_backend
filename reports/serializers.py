# ===============================================
# reports/serializers.py (Final Updated — 2025-10-26)
# ===============================================
# Combines Performance + Feedback + Employee data
# for weekly, monthly, manager-wise, department-wise,
# and employee history reports.
# Fully aligned with frontend and API validation.
# ===============================================

from rest_framework import serializers
from performance.models import PerformanceEvaluation
from feedback.models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee
from .models import CachedReport


# =====================================================
# ✅ 1. BASIC EMPLOYEE SERIALIZER (Used Across Reports)
# =====================================================
class SimpleEmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    emp_id = serializers.CharField(source="user.emp_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "emp_id", "full_name", "email", "department_name"]

    def get_full_name(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return "-"
        return f"{user.first_name or ''} {user.last_name or ''}".strip()


# =====================================================
# ✅ 2. WEEKLY REPORT SERIALIZER
# =====================================================
class WeeklyReportSerializer(serializers.Serializer):
    """Represents a single week's consolidated employee performance."""
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    remarks = serializers.CharField(allow_blank=True, allow_null=True, required=False)


# =====================================================
# ✅ 3. MONTHLY REPORT SERIALIZER
# =====================================================
class MonthlyReportSerializer(serializers.Serializer):
    """Aggregated monthly performance and feedback summary."""
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    avg_score = serializers.FloatField()
    feedback_avg = serializers.FloatField(required=False)
    best_week = serializers.IntegerField()
    best_week_score = serializers.FloatField()


# =====================================================
# ✅ 4. EMPLOYEE HISTORY SERIALIZER
# =====================================================
class EmployeeHistorySerializer(serializers.Serializer):
    """Weekly trend view for an employee’s performance timeline."""
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    remarks = serializers.CharField(allow_null=True)
    rank = serializers.IntegerField(allow_null=True)


# =====================================================
# ✅ 5. MANAGER-WISE REPORT SERIALIZER
# =====================================================
class ManagerReportSerializer(serializers.Serializer):
    """Weekly report for all employees under a specific manager."""
    manager_full_name = serializers.CharField()
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    remarks = serializers.CharField(allow_blank=True, allow_null=True)


# =====================================================
# ✅ 6. DEPARTMENT-WISE REPORT SERIALIZER
# =====================================================
class DepartmentReportSerializer(serializers.Serializer):
    """Weekly report across all employees in a department."""
    department_name = serializers.CharField()
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    manager_full_name = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True)
    remarks = serializers.CharField(allow_blank=True, allow_null=True)


# =====================================================
# ✅ 7. CACHED REPORT SERIALIZER (DB MODEL)
# =====================================================
class CachedReportSerializer(serializers.ModelSerializer):
    """Handles serialization of precomputed/cached reports."""
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
        """Readable period text for dashboards and exports."""
        if obj.report_type in ["weekly", "manager", "department"] and obj.week_number:
            return f"Week {obj.week_number}, {obj.year}"
        if obj.report_type == "monthly" and obj.month:
            return f"Month {obj.month}, {obj.year}"
        return str(obj.year)


# =====================================================
# ✅ 8. COMBINED / AGGREGATED REPORT SERIALIZER
# =====================================================
class CombinedReportSerializer(serializers.Serializer):
    """Combines performance + feedback data into a single analytic payload."""
    type = serializers.ChoiceField(choices=["weekly", "monthly", "manager", "department"])
    year = serializers.IntegerField()
    week_or_month = serializers.IntegerField()
    generated_by_full_name = serializers.CharField()
    total_employees = serializers.IntegerField()
    average_org_score = serializers.FloatField()
    top_performers = serializers.ListField(child=serializers.CharField())
    weak_performers = serializers.ListField(child=serializers.CharField())
    feedback_summary = serializers.DictField(child=serializers.FloatField())

    def validate(self, data):
        """Ensure numeric bounds for week/month."""
        report_type = data.get("type")
        period = data.get("week_or_month")

        if report_type in ["weekly", "manager", "department"] and not (1 <= period <= 53):
            raise serializers.ValidationError({"week_or_month": "Invalid week number (must be 1–53)."})
        if report_type == "monthly" and not (1 <= period <= 12):
            raise serializers.ValidationError({"week_or_month": "Invalid month (must be 1–12)."})
        return data
