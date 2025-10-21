# reports/models.py
from django.db import models
from django.conf import settings


class CachedReport(models.Model):
    """
    Stores precomputed weekly or monthly performance/feedback reports.
    Used to avoid expensive repeated queries (cron/Celery can regenerate).
    """

    REPORT_TYPE_CHOICES = [
        ("weekly", "Weekly Report"),
        ("monthly", "Monthly Report"),
    ]

    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    year = models.PositiveSmallIntegerField()
    week_number = models.PositiveSmallIntegerField(null=True, blank=True)
    month = models.PositiveSmallIntegerField(null=True, blank=True)
    payload = models.JSONField(help_text="Cached JSON data (aggregated summary)")

    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cached_reports",
        help_text="User or system that generated this report",
    )

    file_path = models.FileField(
        upload_to="reports/",
        null=True,
        blank=True,
        help_text="Optional link to a stored PDF/Excel report",
    )

    is_active = models.BooleanField(default=True, help_text="Mark report as active or archived")

    class Meta:
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["report_type", "year", "week_number", "month"],
                name="unique_cached_report_per_period",
            ),
        ]
        verbose_name = "Cached Report"
        verbose_name_plural = "Cached Reports"
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["week_number"]),
            models.Index(fields=["month"]),
        ]

    def __str__(self):
        if self.report_type == "weekly" and self.week_number:
            return f"Weekly Report - Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"Monthly Report - {self.month}/{self.year}"
        return f"{self.report_type.title()} Report ({self.year})"

    def get_period_display(self):
        """Return a formatted display string for the report period."""
        if self.report_type == "weekly" and self.week_number:
            return f"Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"Month {self.month}, {self.year}"
        return str(self.year)
