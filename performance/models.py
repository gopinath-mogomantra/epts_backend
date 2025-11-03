# ===========================================================
# performance/models.py (Enhanced Version — 01-Nov-2025)
# ===========================================================
"""
Performance Evaluation System

This module manages employee performance tracking with weekly evaluations.

Key Features:
  • Weekly performance metrics tracking (15 metrics)
  • Multiple evaluation types (Admin, Manager, Client, Self)
  • Automatic score calculation and ranking
  • Department and organization-wide rankings
  • Historical performance tracking
  • Validation and data integrity checks

Metrics Tracked:
  1. Communication Skills      6. Productivity         11. Attitude
  2. Multitasking             7. Creativity           12. Cooperation
  3. Team Skills              8. Work Quality         13. Dependability
  4. Technical Skills         9. Professionalism      14. Attendance
  5. Job Knowledge           10. Work Consistency     15. Punctuality

Scoring:
  - Each metric: 0-100 points
  - Total score: 0-1500 points (sum of all metrics)
  - Average score: 0-100% (normalized)
  - Ranking: Automatic within department/organization
"""
# ===========================================================

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q, F, Window
from django.db.models.functions import Rank
from datetime import timedelta, date
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# -----------------------------------------------------------
# Constants
# -----------------------------------------------------------
METRIC_MIN_VALUE = 0
METRIC_MAX_VALUE = 100
TOTAL_METRICS_COUNT = 15
MAX_POSSIBLE_SCORE = METRIC_MAX_VALUE * TOTAL_METRICS_COUNT  # 1500

# Performance rating thresholds
RATING_THRESHOLDS = {
    'Outstanding': 90,
    'Exceeds Expectations': 80,
    'Meets Expectations': 70,
    'Needs Improvement': 60,
    'Unsatisfactory': 0,
}


# -----------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------
def current_week_number():
    """Return the current ISO week number (1-53)."""
    return timezone.now().isocalendar()[1]


def current_year():
    """Return the current year."""
    return timezone.now().year


def get_week_range(input_date):
    """
    Return start and end dates for the ISO week of the given date.
    
    Args:
        input_date: Date object to get week range for
        
    Returns:
        tuple: (start_date, end_date) where start is Monday and end is Sunday
    """
    if not input_date:
        input_date = timezone.localdate()
    
    # ISO week starts on Monday (weekday 0)
    start = input_date - timedelta(days=input_date.weekday())
    end = start + timedelta(days=6)
    
    return start, end


def get_performance_rating(average_score):
    """
    Get performance rating based on average score.
    
    Args:
        average_score: Float between 0-100
        
    Returns:
        str: Performance rating label
    """
    for rating, threshold in RATING_THRESHOLDS.items():
        if average_score >= threshold:
            return rating
    return 'Unsatisfactory'


# -----------------------------------------------------------
# PERFORMANCE EVALUATION MODEL
# -----------------------------------------------------------
class PerformanceEvaluation(models.Model):
    """
    Stores weekly performance evaluation data for employees.
    
    Business Rules:
      - One record per employee per week per evaluation_type
      - All metrics are scored 0-100
      - Automatic score calculation on save
      - Automatic ranking within department/organization
      - Week numbers follow ISO 8601 standard
    
    Relationships:
      - Many evaluations → One employee
      - Many evaluations → One evaluator (optional)
      - Many evaluations → One department (optional)
    """

    # -------------------------------------------------------
    # Relations
    # -------------------------------------------------------
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="performance_evaluations",
        db_index=True,
        help_text="Employee whose performance is being evaluated.",
    )
    
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_evaluations",
        help_text="Person who conducted the evaluation (Admin/Manager/Client).",
    )
    
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_performances",
        db_index=True,
        help_text="Department under which the evaluation is recorded.",
    )

    # -------------------------------------------------------
    # Period Information
    # -------------------------------------------------------
    review_date = models.DateField(
        default=timezone.localdate,
        help_text="Date when the evaluation was conducted."
    )
    
    week_number = models.PositiveSmallIntegerField(
        default=current_week_number,
        validators=[MinValueValidator(1), MaxValueValidator(53)],
        help_text="ISO week number (1-53)."
    )
    
    year = models.PositiveSmallIntegerField(
        default=current_year,
        validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        help_text="Year of the evaluation."
    )
    
    evaluation_period = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Human-readable period (e.g., 'Week 41 (07 Oct - 13 Oct 2025)').",
    )

    EVALUATION_TYPE_CHOICES = [
        ("Admin", "Admin Evaluation"),
        ("Manager", "Manager Evaluation"),
        ("Client", "Client Feedback"),
        ("Self", "Self Assessment"),
    ]
    
    evaluation_type = models.CharField(
        max_length=20,
        choices=EVALUATION_TYPE_CHOICES,
        default="Manager",
        db_index=True,
        help_text="Type of evaluation conducted.",
    )

    # -------------------------------------------------------
    # Performance Metrics (0-100 each)
    # -------------------------------------------------------
    # Communication & Interpersonal
    communication_skills = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Verbal and written communication effectiveness (0-100)."
    )
    
    team_skills = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Ability to work collaboratively in teams (0-100)."
    )
    
    cooperation = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Willingness to cooperate with others (0-100)."
    )
    
    attitude = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall work attitude and positivity (0-100)."
    )
    
    professionalism = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Professional conduct and behavior (0-100)."
    )

    # Technical & Job Performance
    technical_skills = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Technical competency and expertise (0-100)."
    )
    
    job_knowledge = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Understanding of job responsibilities (0-100)."
    )
    
    work_quality = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quality and accuracy of work output (0-100)."
    )
    
    work_consistency = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Consistency in maintaining standards (0-100)."
    )

    # Productivity & Innovation
    productivity = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Work output and efficiency (0-100)."
    )
    
    multitasking = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Ability to manage multiple tasks (0-100)."
    )
    
    creativity = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Innovation and problem-solving creativity (0-100)."
    )

    # Reliability & Attendance
    dependability = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Reliability and trustworthiness (0-100)."
    )
    
    attendance = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Regularity and presence at work (0-100)."
    )
    
    punctuality = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Timeliness and punctuality (0-100)."
    )

    # -------------------------------------------------------
    # Computed Fields
    # -------------------------------------------------------
    total_score = models.PositiveIntegerField(
        default=0,
        help_text="Sum of all metric scores (max 1500).",
        editable=False,
    )
    
    average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Average score normalized to 0-100 scale.",
        editable=False,
    )
    
    performance_rating = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Performance rating based on average score.",
        editable=False,
    )
    
    rank = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Rank within department for this week/type.",
        editable=False,
    )
    
    overall_rank = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Organization-wide rank for this week/type.",
        editable=False,
    )
    
    remarks = models.TextField(
        blank=True,
        null=True,
        help_text="Additional comments or feedback from evaluator."
    )

    # -------------------------------------------------------
    # Audit Fields
    # -------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_evaluations",
        help_text="User who created this evaluation.",
    )
    
    is_finalized = models.BooleanField(
        default=False,
        help_text="Whether the evaluation is finalized (locked from editing)."
    )

    # -------------------------------------------------------
    # Meta Configuration
    # -------------------------------------------------------
    class Meta:
        ordering = ["-review_date", "-average_score", "employee__user__emp_id"]
        verbose_name = "Performance Evaluation"
        verbose_name_plural = "Performance Evaluations"
        
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "week_number", "year", "evaluation_type"],
                name="unique_employee_week_eval_type"
            ),
            models.CheckConstraint(
                check=Q(week_number__gte=1) & Q(week_number__lte=53),
                name="valid_week_number"
            ),
            models.CheckConstraint(
                check=Q(average_score__gte=0) & Q(average_score__lte=100),
                name="valid_average_score"
            ),
        ]
        
        indexes = [
            models.Index(fields=["employee", "week_number", "year"]),
            models.Index(fields=["department", "week_number", "year"]),
            models.Index(fields=["evaluation_type", "average_score"]),
            models.Index(fields=["-average_score"]),
            models.Index(fields=["review_date"]),
            models.Index(fields=["is_finalized"]),
        ]

    # -------------------------------------------------------
    # Properties
    # -------------------------------------------------------
    @property
    def metric_fields(self):
        """Return list of all metric field names."""
        return [
            'communication_skills', 'team_skills', 'cooperation', 'attitude',
            'professionalism', 'technical_skills', 'job_knowledge', 'work_quality',
            'work_consistency', 'productivity', 'multitasking', 'creativity',
            'dependability', 'attendance', 'punctuality'
        ]

    @property
    def metric_categories(self):
        """Return metrics grouped by category."""
        return {
            'Communication & Interpersonal': [
                'communication_skills', 'team_skills', 'cooperation',
                'attitude', 'professionalism'
            ],
            'Technical & Job Performance': [
                'technical_skills', 'job_knowledge', 'work_quality', 'work_consistency'
            ],
            'Productivity & Innovation': [
                'productivity', 'multitasking', 'creativity'
            ],
            'Reliability & Attendance': [
                'dependability', 'attendance', 'punctuality'
            ],
        }

    @property
    def is_editable(self):
        """Check if evaluation can be edited."""
        return not self.is_finalized

    @property
    def week_date_range(self):
        """Get the date range for this evaluation's week."""
        return get_week_range(self.review_date)

    # -------------------------------------------------------
    # Validation
    # -------------------------------------------------------
    def clean(self):
        """Validate all metrics are within acceptable range."""
        errors = {}
        
        # Validate each metric
        for field in self.metric_fields:
            value = getattr(self, field, 0)
            if value is None:
                value = 0
                setattr(self, field, value)
            
            if not (METRIC_MIN_VALUE <= value <= METRIC_MAX_VALUE):
                errors[field] = f"Must be between {METRIC_MIN_VALUE} and {METRIC_MAX_VALUE}."
        
        # Validate week number
        if not (1 <= self.week_number <= 53):
            errors['week_number'] = "Week number must be between 1 and 53."
        
        # Validate year
        if not (2000 <= self.year <= 2100):
            errors['year'] = "Year must be between 2000 and 2100."
        
        # Validate review date is not in future
        if self.review_date and self.review_date > timezone.localdate():
            errors['review_date'] = "Review date cannot be in the future."
        
        # Validate department matches employee's department
        if self.employee and not self.department:
            if hasattr(self.employee, 'department') and self.employee.department:
                self.department = self.employee.department
        
        if errors:
            raise ValidationError(errors)

    # -------------------------------------------------------
    # Score Calculation
    # -------------------------------------------------------
    def calculate_scores(self):
        """
        Calculate total and average scores from all metrics.
        
        Returns:
            tuple: (total_score, average_score, performance_rating)
        """
        # Sum all metric values
        metric_values = [getattr(self, field, 0) or 0 for field in self.metric_fields]
        total = sum(metric_values)
        
        # Calculate average (normalized to 0-100)
        average = Decimal(str((total / MAX_POSSIBLE_SCORE) * 100))
        average = average.quantize(Decimal('0.01'))  # Round to 2 decimal places
        
        # Determine performance rating
        rating = get_performance_rating(float(average))
        
        # Update instance fields
        self.total_score = total
        self.average_score = average
        self.performance_rating = rating
        
        return total, average, rating

    # -------------------------------------------------------
    # Ranking Methods
    # -------------------------------------------------------
    def calculate_department_rank(self):
        """
        Calculate rank within department for this week/year/evaluation_type.
        
        Returns:
            int: Rank position (1-based)
        """
        if not self.department:
            return None
        
        evaluations = PerformanceEvaluation.objects.filter(
            department=self.department,
            week_number=self.week_number,
            year=self.year,
            evaluation_type=self.evaluation_type,
        ).order_by('-average_score', 'employee__user__emp_id')
        
        for rank, evaluation in enumerate(evaluations, start=1):
            if evaluation.pk == self.pk:
                return rank
        
        return None

    def calculate_overall_rank(self):
        """
        Calculate organization-wide rank for this week/year/evaluation_type.
        
        Returns:
            int: Overall rank position (1-based)
        """
        evaluations = PerformanceEvaluation.objects.filter(
            week_number=self.week_number,
            year=self.year,
            evaluation_type=self.evaluation_type,
        ).order_by('-average_score', 'employee__user__emp_id')
        
        for rank, evaluation in enumerate(evaluations, start=1):
            if evaluation.pk == self.pk:
                return rank
        
        return None

    def update_ranks(self):
        """Update both department and overall ranks."""
        self.rank = self.calculate_department_rank()
        self.overall_rank = self.calculate_overall_rank()

    @classmethod
    def recalculate_all_ranks(cls, department=None, week_number=None, year=None, evaluation_type=None):
        """
        Recalculate ranks for a group of evaluations.
        
        Args:
            department: Filter by department
            week_number: Filter by week
            year: Filter by year
            evaluation_type: Filter by evaluation type
        """
        filters = {}
        if department:
            filters['department'] = department
        if week_number:
            filters['week_number'] = week_number
        if year:
            filters['year'] = year
        if evaluation_type:
            filters['evaluation_type'] = evaluation_type
        
        evaluations = cls.objects.filter(**filters)
        
        for evaluation in evaluations:
            evaluation.update_ranks()
            evaluation.save(update_fields=['rank', 'overall_rank'])
        
        logger.info(f"Recalculated ranks for {evaluations.count()} evaluations")

    # -------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------
    def get_metric_summary(self):
        """
        Return compact summary of key metrics for dashboards.
        
        Returns:
            dict: Key metric values
        """
        return {
            'employee_id': self.employee.user.emp_id if self.employee else None,
            'week': self.week_number,
            'year': self.year,
            'evaluation_type': self.evaluation_type,
            'metrics': {
                'communication': self.communication_skills,
                'teamwork': self.team_skills,
                'technical': self.technical_skills,
                'productivity': self.productivity,
                'creativity': self.creativity,
                'quality': self.work_quality,
                'attendance': self.attendance,
            },
            'scores': {
                'total': self.total_score,
                'average': float(self.average_score),
                'rating': self.performance_rating,
            },
            'rankings': {
                'department': self.rank,
                'overall': self.overall_rank,
            },
        }

    def get_category_averages(self):
        """
        Calculate average score for each metric category.
        
        Returns:
            dict: Category names mapped to average scores
        """
        category_averages = {}
        
        for category, fields in self.metric_categories.items():
            values = [getattr(self, field, 0) for field in fields]
            average = sum(values) / len(values) if values else 0
            category_averages[category] = round(average, 2)
        
        return category_averages

    def get_strengths_and_weaknesses(self, top_n=3):
        """
        Identify top strengths and weaknesses based on metric scores.
        
        Args:
            top_n: Number of top/bottom metrics to return
            
        Returns:
            dict: {'strengths': [...], 'weaknesses': [...]}
        """
        metric_scores = {
            field.replace('_', ' ').title(): getattr(self, field, 0)
            for field in self.metric_fields
        }
        
        sorted_metrics = sorted(metric_scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'strengths': sorted_metrics[:top_n],
            'weaknesses': sorted_metrics[-top_n:][::-1],
        }

    def finalize(self):
        """Mark evaluation as finalized (locked from editing)."""
        self.is_finalized = True
        self.save(update_fields=['is_finalized', 'updated_at'])
        logger.info(f"Evaluation finalized: {self}")

    def unfinalize(self):
        """Unlock evaluation for editing."""
        self.is_finalized = False
        self.save(update_fields=['is_finalized', 'updated_at'])
        logger.info(f"Evaluation unlocked: {self}")

    # -------------------------------------------------------
    # Save Override
    # -------------------------------------------------------
    def save(self, *args, **kwargs):
        """
        Auto-calculate scores, week/year, and evaluation period before saving.
        """
        # Ensure week_number/year reflect review_date
        if self.review_date:
            iso = self.review_date.isocalendar()
            self.week_number = iso[1]
            self.year = iso[0]
        
        # Auto-set department from employee if not provided
        if not self.department and self.employee:
            if hasattr(self.employee, 'department') and self.employee.department:
                self.department = self.employee.department
        
        # Calculate scores
        self.calculate_scores()
        
        # Auto-generate readable evaluation period
        if not self.evaluation_period and self.review_date:
            start, end = get_week_range(self.review_date)
            self.evaluation_period = (
                f"Week {self.week_number} ({start.strftime('%d %b')} - {end.strftime('%d %b %Y')})"
            )
        
        # Save the instance
        super().save(*args, **kwargs)
        
        # Log save event
        logger.debug(
            f"[PerformanceEval] Saved {self.employee.user.emp_id if self.employee else 'Unknown'} | "
            f"Avg: {self.average_score}% | Rating: {self.performance_rating} | "
            f"Dept: {self.department.code if self.department else 'N/A'}"
        )

    # -------------------------------------------------------
    # String Representation
    # -------------------------------------------------------
    def __str__(self):
        emp_name = "Unknown Employee"
        if self.employee and hasattr(self.employee, "user"):
            emp_name = f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if not emp_name:
                emp_name = self.employee.user.emp_id
        
        return (
            f"{emp_name} - {self.evaluation_type} - "
            f"Week {self.week_number}/{self.year} ({self.average_score}%)"
        )

    def __repr__(self):
        return (
            f"<PerformanceEvaluation: {self.pk} | "
            f"Employee: {self.employee.user.emp_id if self.employee else 'N/A'} | "
            f"Score: {self.average_score}% | "
            f"Rank: {self.rank}>"
        )