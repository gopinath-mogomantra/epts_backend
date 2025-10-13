# performance/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class PerformanceEvaluation(models.Model):
    """
    Stores employee performance data (raw metrics + computed total score).
    Used for performance tracking and ranking (Top/Weak performers).
    """

    emp = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='performance_evaluations'
    )

    department = models.ForeignKey(
        'employee.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performance_evaluations'
    )

    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_performance_reviews'
    )

    review_date = models.DateField(default=timezone.now)
    evaluation_period = models.CharField(
        max_length=120,
        blank=True,
        default='',
        help_text="For example: WK:10/Nov/2025 - 16/Nov/2025"
    )

    # === 15 metrics (each scored 0–100) ===
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

    # Computed total score (out of 1500)
    total_score = models.PositiveIntegerField(default=0, help_text="Sum of all 15 metrics (max 1500)")

    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-review_date', '-created_at']
        verbose_name = 'Performance Evaluation'
        verbose_name_plural = 'Performance Evaluations'

    def calculate_total_score(self):
        """
        Automatically sum all metrics to compute total score.
        """
        metrics = [
            self.communication_skills,
            self.multitasking,
            self.team_skills,
            self.technical_skills,
            self.job_knowledge,
            self.productivity,
            self.creativity,
            self.work_quality,
            self.professionalism,
            self.work_consistency,
            self.attitude,
            self.cooperation,
            self.dependability,
            self.attendance,
            self.punctuality,
        ]
        return sum(int(x) for x in metrics if x is not None)

    def save(self, *args, **kwargs):
        """
        Overridden save method ensures that total_score
        is always recalculated when data changes.
        """
        self.total_score = self.calculate_total_score()
        super().save(*args, **kwargs)

    def __str__(self):
        emp_name = getattr(self.emp, 'username', str(self.emp))
        return f"{emp_name} - {self.review_date} - {self.total_score}/1500"
