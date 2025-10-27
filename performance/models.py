# ===========================================================
# performance/models.py  (Final Updated — Auto-Ranking Ready)
# ===========================================================
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta


# -----------------------------------------------------------
# Helper functions
# -----------------------------------------------------------
def current_week_number():
    """Return the current ISO week number."""
    return timezone.now().isocalendar()[1]


def current_year():
    """Return the current year."""
    return timezone.now().year


def get_week_range(date):
    """Return start and end dates for the week of given date."""
    start = date - timedelta(days=date.weekday())  # Monday
    end = start + timedelta(days=6)  # Sunday
    return start, end


# -----------------------------------------------------------
# PERFORMANCE EVALUATION MODEL
# -----------------------------------------------------------
class PerformanceEvaluation(models.Model):
    """
    Stores weekly performance data for each employee.
    One record per employee per week per evaluation_type.
    """

    # -------------------------------------------------------
    # Relations
    # -------------------------------------------------------
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="performance_evaluations",
        help_text="Employee whose performance is being evaluated.",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_evaluations",
        help_text="Admin, Manager, or Client who gave the evaluation.",
    )
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_performances",
        help_text="Department under which the evaluation is recorded.",
    )

    # -------------------------------------------------------
    # Period Info
    # -------------------------------------------------------
    review_date = models.DateField(default=timezone.localdate)
    week_number = models.PositiveSmallIntegerField(default=current_week_number)
    year = models.PositiveSmallIntegerField(default=current_year)
    evaluation_period = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="E.g., Week 41 (07 Oct 2025 - 13 Oct 2025)",
    )

    EVALUATION_TYPE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Client", "Client"),
        ("Self", "Self"),
    ]
    evaluation_type = models.CharField(
        max_length=20,
        choices=EVALUATION_TYPE_CHOICES,
        default="Manager",
        help_text="Who conducted the evaluation.",
    )

    # -------------------------------------------------------
    # Performance Metrics (0–100)
    # -------------------------------------------------------
    communication_skills = models.PositiveSmallIntegerField(default=0)
    multitasking = models.PositiveSmallIntegerField(default=0)
    team_skills = models.PositiveSmallIntegerField(default=0)
    technical_skills = models.PositiveSmallIntegerField(default=0)
    job_knowledge = models.PositiveSmallIntegerField(default=0)
    productivity = models.PositiveSmallIntegerField(default=0)
    creativity = models.PositiveSmallIntegerField(default=0)
    work_quality = models.PositiveSmallIntegerField(default=0)
    professionalism = models.PositiveSmallIntegerField(default=0)
    work_consistency = models.PositiveSmallIntegerField(default=0)
    attitude = models.PositiveSmallIntegerField(default=0)
    cooperation = models.PositiveSmallIntegerField(default=0)
    dependability = models.PositiveSmallIntegerField(default=0)
    attendance = models.PositiveSmallIntegerField(default=0)
    punctuality = models.PositiveSmallIntegerField(default=0)

    # -------------------------------------------------------
    # Computed Fields
    # -------------------------------------------------------
    total_score = models.PositiveIntegerField(default=0, help_text="Sum of all metrics (max 1500).")
    average_score = models.FloatField(default=0.0, help_text="Average score scaled to 100.")
    rank = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Ranking within department/week.")
    remarks = models.TextField(blank=True, null=True)

    # -------------------------------------------------------
    # Audit Fields
    # -------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -------------------------------------------------------
    # Meta Configuration
    # -------------------------------------------------------
    class Meta:
        ordering = ["-review_date", "-created_at"]
        verbose_name = "Performance Evaluation"
        verbose_name_plural = "Performance Evaluations"
        unique_together = ("employee", "week_number", "year", "evaluation_type")
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["department"]),
            models.Index(fields=["week_number", "year"]),
            models.Index(fields=["evaluation_type"]),
            models.Index(fields=["average_score"]),
        ]

    # -------------------------------------------------------
    # Validation
    # -------------------------------------------------------
    def clean(self):
        """Ensure each metric is between 0 and 100."""
        for field in [
            "communication_skills", "multitasking", "team_skills", "technical_skills",
            "job_knowledge", "productivity", "creativity", "work_quality",
            "professionalism", "work_consistency", "attitude", "cooperation",
            "dependability", "attendance", "punctuality",
        ]:
            value = getattr(self, field)
            if value < 0 or value > 100:
                raise ValidationError({field: "Each metric must be between 0 and 100."})

    # -------------------------------------------------------
    # Score Calculation
    # -------------------------------------------------------
    def calculate_total_score(self):
        """Calculate total and average scores for all metrics."""
        metrics = [
            self.communication_skills, self.multitasking, self.team_skills,
            self.technical_skills, self.job_knowledge, self.productivity,
            self.creativity, self.work_quality, self.professionalism,
            self.work_consistency, self.attitude, self.cooperation,
            self.dependability, self.attendance, self.punctuality,
        ]
        total = sum(int(x or 0) for x in metrics)
        self.total_score = total
        self.average_score = round((total / 1500) * 100, 2)
        return total

    # -------------------------------------------------------
    # Rank Calculation (Manual trigger if needed)
    # -------------------------------------------------------
    def calculate_rank(self):
        """Compute rank within the same department/week manually."""
        evaluations = PerformanceEvaluation.objects.filter(
            department=self.department,
            week_number=self.week_number,
            year=self.year,
            evaluation_type=self.evaluation_type,
        ).order_by("-average_score", "employee__user__first_name")

        for index, eval_obj in enumerate(evaluations, start=1):
            eval_obj.rank = index
            eval_obj.save(update_fields=["rank"])
        return self.rank

    # -------------------------------------------------------
    # Auto-Ranking Helper (Used by Signals)
    # -------------------------------------------------------
    def auto_rank_trigger(self):
        """Trigger ranking recalculation for this record’s department/week."""
        if not self.department:
            return
        evaluations = PerformanceEvaluation.objects.filter(
            department=self.department,
            week_number=self.week_number,
            year=self.year,
        ).order_by("-average_score", "employee__user__first_name")

        for i, record in enumerate(evaluations, start=1):
            if record.rank != i:
                record.rank = i
                record.save(update_fields=["rank"])

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------
    def get_metric_summary(self):
        """Return compact JSON summary for reports/dashboards."""
        return {
            "communication": self.communication_skills,
            "teamwork": self.team_skills,
            "productivity": self.productivity,
            "creativity": self.creativity,
            "attendance": self.attendance,
            "quality": self.work_quality,
            "average": self.average_score,
            "rank": self.rank,
        }

    def department_rank(self):
        """Return department rank position for this employee."""
        qs = PerformanceEvaluation.objects.filter(
            department=self.department,
            week_number=self.week_number,
            year=self.year,
        ).order_by("-average_score")
        return list(qs).index(self) + 1 if self in qs else None

    def overall_rank(self):
        """Return overall organization-wide rank."""
        qs = PerformanceEvaluation.objects.filter(
            week_number=self.week_number,
            year=self.year,
        ).order_by("-average_score")
        return list(qs).index(self) + 1 if self in qs else None

    # -------------------------------------------------------
    # Save Override
    # -------------------------------------------------------
    def save(self, *args, **kwargs):
        """Auto-calculate total, average, and readable period before saving."""
        self.calculate_total_score()

        # ✅ Department fallback (if not manually set)
        if not self.department and self.employee and self.employee.department:
            self.department = self.employee.department

        # ✅ Auto-generate readable evaluation period
        if not self.evaluation_period:
            start, end = get_week_range(self.review_date)
            self.evaluation_period = (
                f"Week {self.week_number} ({start.strftime('%d %b')} - {end.strftime('%d %b %Y')})"
            )

        super().save(*args, **kwargs)

        # Debug log (for console testing)
        print(
            f"[Auto-Rank] Saved {self.employee.user.emp_id} | Avg: {self.average_score} | Dept: {self.department.code if self.department else '-'}"
        )

    # -------------------------------------------------------
    # String Representation
    # -------------------------------------------------------
    def __str__(self):
        emp_name = (
            f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if self.employee and hasattr(self.employee, "user")
            else "Unknown Employee"
        )
        return f"{emp_name} - {self.evaluation_type} ({self.average_score}%)"
