# ===============================================
# performance/models.py (Final Polished Version)
# ===============================================

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


# -------------------------------------------------
# ✅ Helper functions
# -------------------------------------------------
def current_week_number():
    return timezone.now().isocalendar()[1]

def current_year():
    return timezone.now().year


# -------------------------------------------------
# ✅ PERFORMANCE EVALUATION MODEL
# -------------------------------------------------
class PerformanceEvaluation(models.Model):
    """
    Stores weekly performance data for each employee.
    One record per employee per week per evaluation_type.
    """

    # --- Foreign Keys ---
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="performance_evaluations",
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
    )

    # --- Evaluation Meta Info ---
    review_date = models.DateField(default=timezone.now)
    evaluation_period = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="E.g., Week 41 (07 Oct 2025 - 13 Oct 2025)",
    )
    week_number = models.PositiveSmallIntegerField(default=current_week_number)
    year = models.PositiveSmallIntegerField(default=current_year)

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

    # --- Performance Metrics (0–100) ---
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

    # --- Computed Fields ---
    total_score = models.PositiveIntegerField(default=0, help_text="Sum of all 15 metrics (max 1500).")
    average_score = models.FloatField(default=0.0, help_text="Average score scaled to 100.")
    rank = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Rank position based on total score.")
    remarks = models.TextField(null=True, blank=True)

    # --- Audit Fields ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-review_date", "-created_at"]
        verbose_name = "Performance Evaluation"
        verbose_name_plural = "Performance Evaluations"
        unique_together = ("employee", "week_number", "year", "evaluation_type")
        indexes = [
            models.Index(fields=["employee"]),
            models.Index(fields=["department"]),
            models.Index(fields=["week_number", "year"]),
        ]

    # -------------------------------------------------
    # 🔹 Validation
    # -------------------------------------------------
    def clean(self):
        for field in [
            "communication_skills", "multitasking", "team_skills", "technical_skills",
            "job_knowledge", "productivity", "creativity", "work_quality",
            "professionalism", "work_consistency", "attitude", "cooperation",
            "dependability", "attendance", "punctuality",
        ]:
            value = getattr(self, field)
            if value < 0 or value > 100:
                raise ValidationError({field: "Each metric must be between 0 and 100."})

    # -------------------------------------------------
    # 🔹 Score Calculation
    # -------------------------------------------------
    def calculate_total_score(self):
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

    def save(self, *args, **kwargs):
        self.calculate_total_score()
        if not self.evaluation_period:
            self.evaluation_period = f"Week {self.week_number} ({self.review_date.strftime('%d %b %Y')})"
        super().save(*args, **kwargs)

    def __str__(self):
        emp_name = (
            f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if self.employee and hasattr(self.employee, "user")
            else "Unknown Employee"
        )
        return f"{emp_name} - {self.evaluation_type} | {self.average_score}%"
