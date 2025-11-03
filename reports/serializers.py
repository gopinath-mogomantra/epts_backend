# reports/serializers.py
from rest_framework import serializers
from performance.models import PerformanceEvaluation
from feedback.models import GeneralFeedback, ManagerFeedback, ClientFeedback
from employee.models import Employee
from .models import CachedReport
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Union
from functools import lru_cache


# =====================================================
# MIXIN — Standardized Score Rounding & Validation
# =====================================================
class ScoreMixin:
    """
    Provides consistent rounding and validation for numeric scores.
    
    Handles edge cases including None, invalid types, and out-of-range values.
    Uses Decimal for precise financial/scoring calculations.
    """

    def round_score(self, value: Any, default: float = 0.0) -> float:
        """
        Round a score to 2 decimal places with fallback handling.
        
        Args:
            value: The value to round (can be int, float, Decimal, str, or None)
            default: Default value to return if conversion fails
            
        Returns:
            Rounded float value or default
        """
        if value is None:
            return default
        
        try:
            # Use Decimal for consistent rounding (avoids floating point issues)
            decimal_val = Decimal(str(value))
            return float(decimal_val.quantize(Decimal("0.01")))
        except (InvalidOperation, TypeError, ValueError):
            # Fallback to standard float rounding
            try:
                return round(float(value), 2)
            except (TypeError, ValueError):
                return default

    def validate_score_range(
        self, 
        value: Any, 
        min_val: float = 0.0, 
        max_val: float = 100.0,
        field_name: str = "score"
    ) -> float:
        """
        Validate that a score falls within expected range.
        
        Args:
            value: Score to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            field_name: Name of field for error messages
            
        Returns:
            Validated score value
            
        Raises:
            serializers.ValidationError: If value is out of range
        """
        if value is None:
            return 0.0
        
        try:
            numeric_value = float(value)
            if not (min_val <= numeric_value <= max_val):
                raise serializers.ValidationError(
                    f"{field_name} must be between {min_val} and {max_val}. Got {numeric_value}."
                )
            return numeric_value
        except (TypeError, ValueError) as e:
            raise serializers.ValidationError(
                f"{field_name} must be a valid number. Error: {str(e)}"
            )

    def safe_round_representation(self, rep: Dict[str, Any], *fields: str) -> Dict[str, Any]:
        """
        Safely round multiple fields in a representation dictionary.
        
        Args:
            rep: Representation dictionary to modify
            *fields: Field names to round
            
        Returns:
            Modified representation dictionary
        """
        for field in fields:
            if field in rep:
                rep[field] = self.round_score(rep.get(field, 0))
        return rep


# =====================================================
# HELPER MIXIN — User Name Formatting
# =====================================================
class UserNameMixin:
    """Provides consistent user name formatting across serializers."""
    
    @staticmethod
    def format_full_name(user: Any, default: str = "-") -> str:
        """
        Format user's full name safely.
        
        Args:
            user: User object with first_name and last_name attributes
            default: Default value if user is None or names are empty
            
        Returns:
            Formatted full name or default
        """
        if not user:
            return default
        
        first = getattr(user, "first_name", "").strip()
        last = getattr(user, "last_name", "").strip()
        
        full_name = f"{first} {last}".strip()
        return full_name if full_name else default


# =====================================================
# 1. BASIC EMPLOYEE SERIALIZER (Used Across Reports)
# =====================================================
class SimpleEmployeeSerializer(serializers.ModelSerializer, ScoreMixin, UserNameMixin):
    """
    Lightweight employee serializer for report listings.
    
    Includes only essential fields to minimize payload size.
    Used as a nested serializer in various report types.
    """
    full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(
        source="department.name", 
        read_only=True, 
        default="-"
    )
    emp_id = serializers.CharField(source="user.emp_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "emp_id", "full_name", "email", "department_name"]

    def get_full_name(self, obj: Employee) -> str:
        """Extract and format employee's full name."""
        return self.format_full_name(getattr(obj, "user", None))


# =====================================================
# 2. WEEKLY REPORT SERIALIZER
# =====================================================
class WeeklyReportSerializer(serializers.Serializer, ScoreMixin):
    """
    Represents a single week's consolidated employee performance.
    
    Aggregates performance scores and feedback for weekly tracking.
    Includes ranking and remarks for management review.
    """
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField(required=False, allow_null=True, default=0.0)
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True, required=False)
    remarks = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    def validate_week_number(self, value: int) -> int:
        """Ensure week number is valid (1-53)."""
        if not (1 <= value <= 53):
            raise serializers.ValidationError("Week number must be between 1 and 53.")
        return value

    def validate_year(self, value: int) -> int:
        """Ensure year is reasonable (2000-2100)."""
        if not (2000 <= value <= 2100):
            raise serializers.ValidationError("Year must be between 2000 and 2100.")
        return value

    def validate_average_score(self, value: float) -> float:
        """Validate average score is within bounds."""
        return self.validate_score_range(value, 0, 100, "average_score")

    def validate_feedback_avg(self, value: Optional[float]) -> float:
        """
        Validate feedback average (supports both 0-10 and 0-100 scales).
        
        Note: Some feedback systems use 0-10, others use 0-100.
        This validator accepts both for backward compatibility.
        """
        if value is None:
            return 0.0
        
        try:
            numeric_value = float(value)
            # Accept either 0-10 or 0-100 scale
            if not ((0 <= numeric_value <= 10) or (0 <= numeric_value <= 100)):
                raise serializers.ValidationError(
                    "feedback_avg must be between 0-10 or 0-100."
                )
            return numeric_value
        except (TypeError, ValueError):
            return 0.0

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Round all numeric scores in the output."""
        rep = super().to_representation(instance)
        return self.safe_round_representation(
            rep, "average_score", "feedback_avg", "total_score"
        )


# =====================================================
# 3. MONTHLY REPORT SERIALIZER
# =====================================================
class MonthlyReportSerializer(serializers.Serializer, ScoreMixin):
    """
    Aggregated monthly performance and feedback summary.
    
    Provides month-level insights including:
    - Average performance across all weeks
    - Best performing week
    - Feedback trends
    """
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    month = serializers.IntegerField()
    year = serializers.IntegerField()
    avg_score = serializers.FloatField()
    feedback_avg = serializers.FloatField(required=False, allow_null=True, default=0.0)
    best_week = serializers.IntegerField(required=False, allow_null=True)
    best_week_score = serializers.FloatField(required=False, allow_null=True)

    def validate_month(self, value: int) -> int:
        """Ensure month is valid (1-12)."""
        if not (1 <= value <= 12):
            raise serializers.ValidationError("Month must be between 1 and 12.")
        return value

    def validate_year(self, value: int) -> int:
        """Ensure year is reasonable (2000-2100)."""
        if not (2000 <= value <= 2100):
            raise serializers.ValidationError("Year must be between 2000 and 2100.")
        return value

    def validate_best_week(self, value: Optional[int]) -> Optional[int]:
        """Ensure best week is valid if provided."""
        if value is not None and not (1 <= value <= 53):
            raise serializers.ValidationError("Best week must be between 1 and 53.")
        return value

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Round all numeric scores in the output."""
        rep = super().to_representation(instance)
        return self.safe_round_representation(
            rep, "avg_score", "feedback_avg", "best_week_score"
        )


# =====================================================
# 4. EMPLOYEE HISTORY SERIALIZER
# =====================================================
class EmployeeHistorySerializer(serializers.Serializer, ScoreMixin):
    """
    Weekly trend view for an employee's performance timeline.
    
    Used for generating performance charts and identifying trends.
    Supports historical analysis and performance forecasting.
    """
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField(required=False, allow_null=True, default=0.0)
    remarks = serializers.CharField(allow_null=True, required=False, allow_blank=True)
    rank = serializers.IntegerField(allow_null=True, required=False)

    def validate_week_number(self, value: int) -> int:
        """Ensure week number is valid."""
        if not (1 <= value <= 53):
            raise serializers.ValidationError("Week number must be between 1 and 53.")
        return value

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Round all numeric scores in the output."""
        rep = super().to_representation(instance)
        return self.safe_round_representation(rep, "average_score", "feedback_avg")


# =====================================================
# 5. MANAGER-WISE REPORT SERIALIZER
# =====================================================
class ManagerReportSerializer(serializers.Serializer, ScoreMixin):
    """
    Weekly report for all employees under a specific manager.
    
    Enables managers to track their team's performance and identify
    areas requiring intervention or recognition.
    """
    manager_full_name = serializers.CharField()
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    department = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField(required=False, allow_null=True, default=0.0)
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True, required=False)
    remarks = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    def validate_week_number(self, value: int) -> int:
        """Ensure week number is valid."""
        if not (1 <= value <= 53):
            raise serializers.ValidationError("Week number must be between 1 and 53.")
        return value

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Round all numeric scores in the output."""
        rep = super().to_representation(instance)
        return self.safe_round_representation(
            rep, "average_score", "feedback_avg", "total_score"
        )


# =====================================================
# 6. DEPARTMENT-WISE REPORT SERIALIZER
# =====================================================
class DepartmentReportSerializer(serializers.Serializer, ScoreMixin):
    """
    Weekly report across all employees in a department.
    
    Provides department heads with comprehensive team overview
    for resource allocation and performance management decisions.
    """
    department_name = serializers.CharField()
    emp_id = serializers.CharField()
    employee_full_name = serializers.CharField()
    manager_full_name = serializers.CharField()
    total_score = serializers.FloatField()
    average_score = serializers.FloatField()
    feedback_avg = serializers.FloatField(required=False, allow_null=True, default=0.0)
    week_number = serializers.IntegerField()
    year = serializers.IntegerField()
    rank = serializers.IntegerField(allow_null=True, required=False)
    remarks = serializers.CharField(allow_blank=True, allow_null=True, required=False)

    def validate_week_number(self, value: int) -> int:
        """Ensure week number is valid."""
        if not (1 <= value <= 53):
            raise serializers.ValidationError("Week number must be between 1 and 53.")
        return value

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Round all numeric scores in the output."""
        rep = super().to_representation(instance)
        return self.safe_round_representation(
            rep, "average_score", "feedback_avg", "total_score"
        )


# =====================================================
# 7. CACHED REPORT SERIALIZER (DB MODEL)
# =====================================================
class CachedReportSerializer(serializers.ModelSerializer, UserNameMixin):
    """
    Handles serialization of precomputed/cached reports.
    
    Caching reduces database load for frequently accessed reports.
    Supports invalidation and regeneration strategies.
    """

    generated_by_full_name = serializers.SerializerMethodField(read_only=True)
    generated_by_name = serializers.CharField(
        source="generated_by.username", 
        read_only=True, 
        default="-"
    )
    period_display = serializers.SerializerMethodField(read_only=True)
    report_label = serializers.SerializerMethodField(read_only=True)
    export_type = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CachedReport
        fields = [
            "id", "report_type", "year", "week_number", "month",
            "manager", "department", "payload", "file_path",
            "generated_at", "generated_by", "generated_by_name",
            "generated_by_full_name", "is_active", "period_display",
            "report_label", "export_type",
        ]
        read_only_fields = [
            "id", "generated_at", "generated_by_name",
            "generated_by_full_name", "period_display", "report_label", "export_type",
        ]

    def get_generated_by_full_name(self, obj: CachedReport) -> str:
        """Format the name of user who generated this report."""
        return self.format_full_name(getattr(obj, "generated_by", None))

    def get_period_display(self, obj: CachedReport) -> str:
        """
        Readable period for dashboards and exports.
        
        Examples: "Week 23, 2024", "January 2024"
        """
        try:
            return obj.get_period_display()
        except (AttributeError, TypeError):
            # Fallback if method doesn't exist
            if obj.week_number:
                return f"Week {obj.week_number}, {obj.year}"
            elif obj.month:
                month_names = [
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"
                ]
                return f"{month_names[obj.month - 1]} {obj.year}"
            return f"{obj.year}"

    def get_report_label(self, obj: CachedReport) -> str:
        """Return contextual label for frontend cards."""
        try:
            return obj.report_scope
        except (AttributeError, TypeError):
            return obj.report_type or "General Report"

    def get_export_type(self, obj: CachedReport) -> str:
        """Return export format (PDF, Excel, CSV, etc.)."""
        try:
            return obj.export_type
        except (AttributeError, TypeError):
            # Infer from file_path if export_type not available
            if hasattr(obj, 'file_path') and obj.file_path:
                ext = obj.file_path.split('.')[-1].upper()
                return ext if ext in ['PDF', 'XLSX', 'CSV', 'JSON'] else '-'
            return "-"


# =====================================================
# 8. COMBINED / AGGREGATED REPORT SERIALIZER
# =====================================================
class CombinedReportSerializer(serializers.Serializer, ScoreMixin):
    """
    Combines performance + feedback + ranking into a single analytic payload.
    
    Used for:
    - Analytics dashboards
    - Power BI integration
    - Executive summaries
    - Trend analysis
    
    Provides comprehensive organizational insights in one payload.
    """
    type = serializers.ChoiceField(
        choices=["weekly", "monthly", "manager", "department"]
    )
    year = serializers.IntegerField()
    week_or_month = serializers.IntegerField()
    generated_by_full_name = serializers.CharField()
    total_employees = serializers.IntegerField(min_value=0)
    average_org_score = serializers.FloatField()
    top_performers = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    weak_performers = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    feedback_summary = serializers.DictField(
        child=serializers.FloatField(),
        required=False,
        default=dict
    )
    top3_ranking = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )
    weak3_ranking = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list
    )

    def validate_year(self, value: int) -> int:
        """Ensure year is reasonable."""
        if not (2000 <= value <= 2100):
            raise serializers.ValidationError("Year must be between 2000 and 2100.")
        return value

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cross-field validation for period consistency.
        
        Ensures week_or_month is valid for the specified report type.
        """
        report_type = data.get("type")
        period = data.get("week_or_month")

        # Validate period based on report type
        if report_type in ["weekly", "manager", "department"]:
            if not isinstance(period, int) or not (1 <= period <= 53):
                raise serializers.ValidationError({
                    "week_or_month": "Invalid week number (must be 1–53)."
                })
        elif report_type == "monthly":
            if not isinstance(period, int) or not (1 <= period <= 12):
                raise serializers.ValidationError({
                    "week_or_month": "Invalid month (must be 1–12)."
                })

        # Validate feedback_summary numeric values
        feedback_summary = data.get("feedback_summary", {})
        for key, value in feedback_summary.items():
            try:
                float_val = float(value)
                # Ensure feedback scores are reasonable
                if not (0 <= float_val <= 100):
                    raise serializers.ValidationError({
                        f"feedback_summary.{key}": "Must be between 0 and 100."
                    })
            except (TypeError, ValueError):
                raise serializers.ValidationError({
                    f"feedback_summary.{key}": "Must be a valid numeric value."
                })

        # Validate top/weak performers lists aren't empty if provided
        if data.get("top_performers") is not None and len(data["top_performers"]) == 0:
            data["top_performers"] = []
        if data.get("weak_performers") is not None and len(data["weak_performers"]) == 0:
            data["weak_performers"] = []

        return data

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """
        Round numeric values and sanitize feedback summary.
        
        Ensures consistent decimal precision across all numeric fields.
        """
        rep = super().to_representation(instance)
        
        # Round main score
        rep["average_org_score"] = self.round_score(rep.get("average_org_score", 0))
        
        # Sanitize and round feedback_summary
        feedback_summary = rep.get("feedback_summary") or {}
        rep["feedback_summary"] = {
            key: self.round_score(value) 
            for key, value in feedback_summary.items()
        }
        
        # Ensure lists exist
        rep.setdefault("top_performers", [])
        rep.setdefault("weak_performers", [])
        rep.setdefault("top3_ranking", [])
        rep.setdefault("weak3_ranking", [])
        
        return rep


# =====================================================
# 9. REPORT SUMMARY SERIALIZER (Optional Enhancement)
# =====================================================
class ReportSummarySerializer(serializers.Serializer, ScoreMixin):
    """
    High-level summary statistics for dashboard widgets.
    
    Provides quick insights without loading full report data:
    - Total employees evaluated
    - Average scores
    - Trends (up/down from previous period)
    - Distribution stats
    """
    period = serializers.CharField()
    total_employees = serializers.IntegerField()
    avg_performance = serializers.FloatField()
    avg_feedback = serializers.FloatField()
    trend = serializers.ChoiceField(choices=["up", "down", "stable"])
    trend_percentage = serializers.FloatField(required=False, allow_null=True)
    top_department = serializers.CharField(required=False, allow_null=True)
    improvement_needed = serializers.IntegerField(default=0)

    def to_representation(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        """Round all numeric scores."""
        rep = super().to_representation(instance)
        return self.safe_round_representation(
            rep, "avg_performance", "avg_feedback", "trend_percentage"
        )