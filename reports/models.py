from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import os


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

    # -----------------------------------------------------------
    # 🔹 Identification Fields
    # -----------------------------------------------------------
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

    # -----------------------------------------------------------
    # 🔹 Optional Relationships
    # -----------------------------------------------------------
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

    # -----------------------------------------------------------
    # 🔹 Cached Payload
    # -----------------------------------------------------------
    payload = models.JSONField(
        help_text="Cached JSON data (aggregated summary, KPIs, and metrics)"
    )

    # -----------------------------------------------------------
    # 🔹 Metadata
    # -----------------------------------------------------------
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

    # -----------------------------------------------------------
    # ⚙️ Model Meta
    # -----------------------------------------------------------
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
        index_together = [
            ("report_type", "year", "week_number"),
            ("report_type", "year", "month"),
        ]

    # -----------------------------------------------------------
    # 🔍 Validation
    # -----------------------------------------------------------
    def clean(self):
        """Ensure the correct combination of fields are set based on report_type."""
        if self.report_type in ["weekly", "manager", "department"] and not self.week_number:
            raise ValidationError("Week number is required for weekly/manager/department reports.")
        if self.report_type == "monthly" and not self.month:
            raise ValidationError("Month is required for monthly reports.")

    # -----------------------------------------------------------
    # 💾 Save Override
    # -----------------------------------------------------------
    def save(self, *args, **kwargs):
        """Update generated_at timestamp and validate before saving."""
        self.full_clean()
        self.generated_at = timezone.now()
        super().save(*args, **kwargs)

    # -----------------------------------------------------------
    # 🪶 Helper: Filename Generator
    # -----------------------------------------------------------
    def generate_filename(self, extension="csv"):
        """Return a clean, unique filename for export."""
        base = f"{self.report_type.title()}_{self.get_period_display()}".replace(" ", "_")
        timestamp = timezone.now().strftime("%Y%m%d_%H%M")
        safe_name = base.replace(":", "").replace(",", "").replace("__", "_")
        return f"{safe_name}_{timestamp}.{extension}"

    # -----------------------------------------------------------
    # 🧩 Helper: Summary Payload (for dashboard cards)
    # -----------------------------------------------------------
    def get_payload_summary(self):
        """Return summarized statistics from the payload."""
        data = self.payload.get("records", [])
        if not data:
            return {"count": 0, "avg_score": 0, "top_emp": None}
        avg_score = round(sum(r.get("average_score", 0) for r in data) / len(data), 2)
        top = max(data, key=lambda r: r.get("average_score", 0), default={})
        return {"count": len(data), "avg_score": avg_score, "top_emp": top.get("employee_full_name")}

    # -----------------------------------------------------------
    # 🧠 Helper: Readable Period
    # -----------------------------------------------------------
    def get_period_display(self):
        """Return formatted label for UI cards and exports."""
        if self.report_type in ["weekly", "manager", "department"] and self.week_number:
            return f"Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"Month {self.month}, {self.year}"
        return str(self.year)

    # -----------------------------------------------------------
    # 🪶 Helper: Scope (UI Label)
    # -----------------------------------------------------------
    @property
    def report_scope(self):
        """Return a detailed label for UI cards and cache management."""
        if self.report_type == "manager" and self.manager:
            return f"Manager: {self.manager.get_full_name()} ({self.get_period_display()})"
        elif self.report_type == "department" and self.department:
            return f"Dept: {self.department.name} ({self.get_period_display()})"
        return f"{self.report_type.title()} ({self.get_period_display()})"

    # -----------------------------------------------------------
    # ♻️ Archive / Restore
    # -----------------------------------------------------------
    def soft_delete(self):
        """Archive a report instead of deleting."""
        self.is_active = False
        self.save(update_fields=["is_active"])

    def restore(self):
        """Re-activate an archived report."""
        self.is_active = True
        self.save(update_fields=["is_active"])

    # -----------------------------------------------------------
    # 📦 Static Utility
    # -----------------------------------------------------------
    @staticmethod
    def get_latest(report_type):
        """Return the most recent active report of a specific type."""
        return CachedReport.objects.filter(
            report_type=report_type, is_active=True
        ).order_by("-generated_at").first()

    # -----------------------------------------------------------
    # 🪪 String Representation
    # -----------------------------------------------------------
    def __str__(self):
        """Readable name for admin, logs, and UI labels."""
        if self.report_type == "weekly" and self.week_number:
            return f"📅 Weekly Report — Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            return f"📊 Monthly Report — Month {self.month}, {self.year}"
        elif self.report_type == "manager" and self.manager:
            return f"👨‍💼 Manager Report — {self.manager.get_full_name()} ({self.get_period_display()})"
        elif self.report_type == "department" and self.department:
            return f"🏢 Department Report — {self.department.name} ({self.get_period_display()})"
        return f"{self.report_type.title()} Report ({self.year})"
