# ===============================================
# reports/models.py  (Frontend & API-Ready)
# ===============================================

from django.db import models
from django.conf import settings
from django.utils import timezone


class CachedReport(models.Model):
    """
    Stores precomputed weekly, monthly, manager-wise, or department-wise
    performance reports for faster analytics and dashboard display.
    """

    REPORT_TYPE_CHOICES = [
        ("weekly", "Weekly Report"),
        ("monthly", "Monthly Report"),
        ("manager", "Manager-wise Report"),
        ("department", "Department-wise Report"),
    ]

    # 🔹 Identification Fields
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        help_text="Type of report (weekly, monthly, manager, department)"
    )
    year = models.PositiveSmallIntegerField(help_text="Report year (e.g., 2025)")
    week_number = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Week number (used for weekly/manager/department reports)"
    )
    month = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Month number (used for monthly reports)"
    )

    # 🔹 Optional Relationships
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="manager_reports",
        help_text="Manager reference for manager-wise reports"
    )
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="department_reports",
        help_text="Department reference for department-wise reports"
    )

    # 🔹 Cached Payload
    payload = models.JSONField(
        help_text="Cached JSON data (aggregated summary, KPIs, and metrics)"
    )

    # 🔹 Metadata
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cached_reports",
        help_text="User or system who generated this report"
    )
    file_path = models.FileField(
        upload_to="reports/",
        null=True, blank=True,
        help_text="Optional path to generated PDF or Excel file"
    )
    is_active = models.BooleanField(default=True, help_text="Active or archived flag")

    class Meta:
        ordering = ["-generated_at"]
        verbose_name = "Cached Report"
        verbose_name_plural = "Cached Reports"
        constraints = [
            models.UniqueConstraint(
                fields=["report_type", "year", "week_number", "month", "manager", "department"],
                name="unique_cached_report_per_period",
            )
        ]
        indexes = [
            models.Index(fields=["year"]),
            models.Index(fields=["month"]),
            models.Index(fields=["week_number"]),
            models.Index(fields=["report_type"]),
        ]

    # ------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------
    def __str__(self):
        """Readable name for admin, logs, and UI labels."""
        if self.report_type == "weekly" and self.week_number:
            return f"📅 Weekly Report — Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"📊 Monthly Report — Month {self.month}, {self.year}"
        elif self.report_type == "manager" and self.manager:
            return f"👨‍💼 Manager Report — {self.manager.get_full_name()} (Week {self.week_number}, {self.year})"
        elif self.report_type == "department" and self.department:
            return f"🏢 Department Report — {self.department.name} (Week {self.week_number}, {self.year})"
        return f"{self.report_type.title()} Report ({self.year})"

    def get_period_display(self):
        """Return formatted label for UI cards and exports."""
        if self.report_type in ["weekly", "manager", "department"] and self.week_number:
            return f"Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"Month {self.month}, {self.year}"
        return str(self.year)

    def soft_delete(self):
        """Archive a report instead of permanent deletion."""
        self.is_active = False
        self.save(update_fields=["is_active"])

    def restore(self):
        """Re-activate an archived report."""
        self.is_active = True
        self.save(update_fields=["is_active"])

    @staticmethod
    def get_latest(report_type):
        """Return the most recent active report of a specific type."""
        return CachedReport.objects.filter(report_type=report_type, is_active=True).order_by("-generated_at").first()
