# ===============================================
# reports/serializers.py
# ===============================================
# Combines data from Performance + Feedback modules
# to generate weekly, monthly, and employee history reports
# ===============================================

from rest_framework import serializers
from django.db.models import Avg, Max
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
        return f"{u.first_name} {u.last_name}".strip()


# -------------------------------------------------
# ✅ 2. Weekly Report Serializer
# -------------------------------------------------
class WeeklyReportSerializer(serializers.Serializer):
    """
    Represents a consolidated weekly report entry per employee.
    Combines performance evaluation scores with feedback averages.
    """
    emp_id = serializers.CharField()
    employee_name = serializers.CharField()
    department = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField()


# -------------------------------------------------
# ✅ 3. Monthly Report Serializer
# -------------------------------------------------
class MonthlyReportSerializer(serializers.Serializer):
    """
    Represents an aggregated monthly summary of performance and feedback.
    Includes best-performing week details.
    """
    emp_id = serializers.CharField()
    employee_name = serializers.CharField()
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
    """
    Represents weekly trend/history data for a single employee.
    Used for graph plotting or performance trend dashboards.
    """
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField()
    remarks = serializers.CharField(allow_null=True)
    rank = serializers.IntegerField(allow_null=True)


# -------------------------------------------------
# ✅ 5. Cached Report Serializer (NEW)
# -------------------------------------------------
class CachedReportSerializer(serializers.ModelSerializer):
    """
    Serializer for cached precomputed reports stored in CachedReport model.
    These reports may include aggregated JSON data (payload) and optional file paths.
    """

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
            "payload",
            "file_path",
            "generated_at",
            "generated_by",
            "generated_by_name",
            "is_active",
            "period_display",
        ]
        read_only_fields = ["generated_at", "generated_by_name", "period_display"]

    def get_period_display(self, obj):
        """Readable label for report period (used in frontend tables)."""
        if obj.report_type == "weekly" and obj.week_number:
            return f"Week {obj.week_number}, {obj.year}"
        elif obj.report_type == "monthly" and obj.month:
            return f"Month {obj.month}, {obj.year}"
        return f"{obj.year}"


# -------------------------------------------------
# ✅ 6. Aggregated Report Helper Serializer (optional)
# -------------------------------------------------
class CombinedReportSerializer(serializers.Serializer):
    """
    Combines weekly or monthly performance + feedback stats into one payload.
    Used when generating reports dynamically without caching.
    """

    type = serializers.ChoiceField(choices=["weekly", "monthly"])
    year = serializers.IntegerField()
    week_or_month = serializers.IntegerField()
    generated_by = serializers.CharField()
    total_employees = serializers.IntegerField()
    average_org_score = serializers.FloatField()
    top_performers = serializers.ListField(child=serializers.CharField())
    weak_performers = serializers.ListField(child=serializers.CharField())
    feedback_summary = serializers.DictField(child=serializers.FloatField())

    def validate(self, data):
        """Ensure week_or_month matches report type."""
        if data["type"] == "weekly" and not (1 <= data["week_or_month"] <= 53):
            raise serializers.ValidationError("Invalid week number (1–53).")
        if data["type"] == "monthly" and not (1 <= data["week_or_month"] <= 12):
            raise serializers.ValidationError("Invalid month (1–12).")
        return data
