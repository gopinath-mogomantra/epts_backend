# ===============================================
# reports/models.py (Final Updated Version)
# ===============================================
from django.db import models
from django.conf import settings


class CachedReport(models.Model):
    """
    Stores precomputed weekly, monthly, manager-wise, or department-wise performance reports.
    Used for analytics caching or PDF/Excel export. Regenerated via cron/Celery if needed.
    """

    REPORT_TYPE_CHOICES = [
        ("weekly", "Weekly Report"),
        ("monthly", "Monthly Report"),
        ("manager", "Manager-wise Report"),
        ("department", "Department-wise Report"),
    ]

    # 🔹 Report Info
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    year = models.PositiveSmallIntegerField(help_text="Report year")
    week_number = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Week number (for weekly/manager/department reports)")
    month = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Month number (for monthly reports)")

    # 🔹 Relationships (optional links for filtering)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manager_reports",
        help_text="Manager for manager-wise reports",
    )

    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_reports",
        help_text="Department for department-wise reports",
    )

    # 🔹 Stored Report Data
    payload = models.JSONField(help_text="Cached JSON data (aggregated summary and metrics)")

    # 🔹 Metadata
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
        help_text="Optional stored PDF/Excel file path",
    )

    is_active = models.BooleanField(default=True, help_text="Mark report as active or archived")

    class Meta:
        ordering = ["-generated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["report_type", "year", "week_number", "month", "manager", "department"],
                name="unique_cached_report_per_period",
            ),
        ]
        verbose_name = "Cached Report"
        verbose_name_plural = "Cached Reports"
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["week_number"]),
            models.Index(fields=["month"]),
            models.Index(fields=["report_type"]),
        ]

    def __str__(self):
        """Readable string for admin / logs."""
        if self.report_type == "weekly" and self.week_number:
            return f"Weekly Report - Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"Monthly Report - {self.month}/{self.year}"
        elif self.report_type == "manager" and self.manager:
            return f"Manager Report - {self.manager.get_full_name()} (Week {self.week_number}, {self.year})"
        elif self.report_type == "department" and self.department:
            return f"Department Report - {self.department.name} (Week {self.week_number}, {self.year})"
        return f"{self.report_type.title()} Report ({self.year})"

    def get_period_display(self):
        """Return a formatted display string for UI/report labels."""
        if self.report_type in ["weekly", "manager", "department"] and self.week_number:
            return f"Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"Month {self.month}, {self.year}"
        return str(self.year)
