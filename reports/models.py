# ===========================================================
# reports/models.py (Enhanced Version — 01-Nov-2025)
# ===========================================================
"""
Report Caching and Management System

This module handles precomputed performance reports for:
  • Weekly performance summaries
  • Monthly aggregated reports
  • Manager-wise team reports
  • Department-wise analytics
  • Custom period reports

Features:
  • JSON payload caching for fast retrieval
  • File attachment support (PDF, Excel)
  • Automatic cache invalidation
  • Soft delete/restore functionality
  • Report versioning
  • Access tracking
  • Compression support
  • Export history
"""
# ===========================================================

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q
from datetime import datetime, date
import os
import json
import hashlib
import logging

logger = logging.getLogger(__name__)


# ===========================================================
# HELPER FUNCTIONS
# ===========================================================
def report_upload_path(instance, filename):
    """Generate organized upload path for report files."""
    year = instance.year
    report_type = instance.report_type
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    
    # Clean filename
    name, ext = os.path.splitext(filename)
    clean_name = "".join(c for c in name if c.isalnum() or c in "._- ")
    
    return f"reports/{year}/{report_type}/{timestamp}_{clean_name}{ext}"


# ===========================================================
# CACHED REPORT MODEL
# ===========================================================
class CachedReport(models.Model):
    """
    Stores precomputed performance reports with caching.
    
    Features:
      - Multiple report types
      - JSON payload caching
      - File attachments (PDF/Excel)
      - Automatic naming
      - Soft delete support
      - Access tracking
      - Cache invalidation
    
    Business Rules:
      - Unique per report_type + period + entity
      - Auto-generate descriptive names
      - Track generation and access
      - Support file cleanup
    """

    REPORT_TYPE_CHOICES = [
        ("weekly", "Weekly Performance Report"),
        ("monthly", "Monthly Performance Report"),
        ("quarterly", "Quarterly Performance Report"),
        ("annual", "Annual Performance Report"),
        ("manager", "Manager Team Report"),
        ("department", "Department Analytics Report"),
        ("employee", "Individual Employee Report"),
        ("custom", "Custom Period Report"),
    ]

    # -----------------------------------------------------------
    # Identification Fields
    # -----------------------------------------------------------
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPE_CHOICES,
        db_index=True,
        help_text="Type of report being cached.",
    )
    
    year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        help_text="Report year (e.g., 2025).",
    )
    
    week_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(53)],
        help_text="ISO week number (1-53) for weekly reports.",
    )
    
    month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Month number (1-12) for monthly reports.",
    )
    
    quarter = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Quarter number (1-4) for quarterly reports.",
    )
    
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Start date for custom period reports.",
    )
    
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date for custom period reports.",
    )

    # -----------------------------------------------------------
    # Relationships
    # -----------------------------------------------------------
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manager_reports",
        help_text="Manager for manager-wise reports.",
    )
    
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_reports",
        help_text="Department for department-wise reports.",
    )
    
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_reports",
        help_text="Employee for individual reports.",
    )

    # -----------------------------------------------------------
    # Cached Data
    # -----------------------------------------------------------
    payload = models.JSONField(
        default=dict,
        help_text="Cached JSON data (aggregated metrics, KPIs, summaries).",
    )
    
    report_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Human-readable report name (auto-generated).",
    )
    
    description = models.TextField(
        blank=True,
        help_text="Optional description or notes about the report.",
    )
    
    report_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of payload for change detection.",
    )

    # -----------------------------------------------------------
    # File Attachments
    # -----------------------------------------------------------
    file_path = models.FileField(
        upload_to=report_upload_path,
        null=True,
        blank=True,
        help_text="Generated PDF/Excel file path.",
    )
    
    file_size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes.",
    )
    
    file_format = models.CharField(
        max_length=10,
        blank=True,
        choices=[
            ("pdf", "PDF"),
            ("xlsx", "Excel"),
            ("csv", "CSV"),
            ("json", "JSON"),
        ],
        help_text="Export file format.",
    )

    # -----------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------
    generated_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the report was generated.",
    )
    
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_reports",
        help_text="User who generated this report.",
    )
    
    version = models.PositiveSmallIntegerField(
        default=1,
        help_text="Report version number (increments on regeneration).",
    )
    
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this report is currently active.",
    )

    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Indicates if this report has been archived (older data).",
    )

    
    access_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times report has been accessed.",
    )
    
    last_accessed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time report was accessed.",
    )
    
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional expiration date for temporary reports.",
    )

    # -----------------------------------------------------------
    # Statistics (from payload)
    # -----------------------------------------------------------
    record_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of records in the report.",
    )
    
    average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Average performance score in report.",
    )

    # -----------------------------------------------------------
    # Meta Configuration
    # -----------------------------------------------------------
    class Meta:
        ordering = ["-generated_at", "-version"]
        verbose_name = "Cached Report"
        verbose_name_plural = "Cached Reports"
        
        constraints = [
            models.UniqueConstraint(
                fields=["report_type", "year", "week_number", "month", "quarter", 
                        "manager", "department", "employee"],
                name="unique_report_per_period_entity",
                condition=Q(is_active=True),
            ),
        ]
        
        indexes = [
            models.Index(fields=["report_type", "year"]),
            models.Index(fields=["year", "month"]),
            models.Index(fields=["year", "week_number"]),
            models.Index(fields=["generated_at"]),
            models.Index(fields=["is_active", "generated_at"]),
            models.Index(fields=["manager", "year"]),
            models.Index(fields=["department", "year"]),
            models.Index(fields=["-access_count"]),
        ]

    # -----------------------------------------------------------
    # Properties
    # -----------------------------------------------------------
    @property
    def period_display(self):
        """Return human-readable period string."""
        if self.report_type in ["weekly", "manager", "department"] and self.week_number:
            return f"Week {self.week_number}, {self.year}"
        elif self.report_type == "monthly" and self.month:
            month_names = [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
            ]
            return f"{month_names[self.month - 1]} {self.year}"
        elif self.report_type == "quarterly" and self.quarter:
            return f"Q{self.quarter} {self.year}"
        elif self.report_type == "annual":
            return f"Year {self.year}"
        elif self.report_type == "custom" and self.start_date and self.end_date:
            return f"{self.start_date.strftime('%d %b')} - {self.end_date.strftime('%d %b %Y')}"
        return str(self.year)

    @property
    def report_scope(self):
        """Return detailed scope description."""
        scope_parts = []
        
        # Add type
        scope_parts.append(self.get_report_type_display())
        
        # Add entity
        if self.manager:
            scope_parts.append(f"Manager: {self.manager.get_full_name()}")
        elif self.department:
            scope_parts.append(f"Department: {self.department.name}")
        elif self.employee:
            scope_parts.append(
                f"Employee: {self.employee.user.first_name} {self.employee.user.last_name}"
            )
        
        # Add period
        scope_parts.append(f"({self.period_display})")
        
        return " - ".join(scope_parts)

    @property
    def export_type(self):
        """Return export format."""
        if self.file_format:
            return self.file_format.upper()
        if not self.file_path:
            return "JSON"
        _, ext = os.path.splitext(self.file_path.name)
        return ext.replace(".", "").upper() or "Unknown"

    @property
    def file_size_display(self):
        """Return formatted file size."""
        if not self.file_size:
            return "N/A"
        
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def is_expired(self):
        """Check if report has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at

    @property
    def age_display(self):
        """Return how old the report is."""
        delta = timezone.now() - self.generated_at
        
        if delta.days == 0:
            hours = delta.seconds // 3600
            if hours == 0:
                minutes = delta.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.days == 1:
            return "Yesterday"
        elif delta.days < 7:
            return f"{delta.days} days ago"
        elif delta.days < 30:
            weeks = delta.days // 7
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif delta.days < 365:
            months = delta.days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = delta.days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"

    # -----------------------------------------------------------
    # Validation
    # -----------------------------------------------------------
    def clean(self):
        """Validate report configuration."""
        errors = {}
        
        # Validate period fields based on report type
        if self.report_type in ["weekly", "manager", "department"]:
            if not self.week_number:
                errors["week_number"] = "Week number is required for weekly/manager/department reports."
        
        if self.report_type == "monthly":
            if not self.month:
                errors["month"] = "Month is required for monthly reports."
        
        if self.report_type == "quarterly":
            if not self.quarter:
                errors["quarter"] = "Quarter is required for quarterly reports."
        
        if self.report_type == "custom":
            if not (self.start_date and self.end_date):
                errors["custom_period"] = "Start and end dates are required for custom reports."
            elif self.start_date > self.end_date:
                errors["custom_period"] = "Start date must be before end date."
        
        # Validate entity fields
        if self.report_type == "manager" and not self.manager:
            errors["manager"] = "Manager is required for manager reports."
        
        if self.report_type == "department" and not self.department:
            errors["department"] = "Department is required for department reports."
        
        if self.report_type == "employee" and not self.employee:
            errors["employee"] = "Employee is required for employee reports."
        
        # Validate dates
        if self.expires_at and self.expires_at <= self.generated_at:
            errors["expires_at"] = "Expiration date must be after generation date."
        
        if errors:
            raise ValidationError(errors)

    # -----------------------------------------------------------
    # Methods
    # -----------------------------------------------------------
    def calculate_hash(self):
        """Calculate SHA-256 hash of payload."""
        payload_str = json.dumps(self.payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def update_file_info(self):
        """Update file size and format from file_path."""
        if self.file_path and os.path.isfile(self.file_path.path):
            self.file_size = os.path.getsize(self.file_path.path)
            _, ext = os.path.splitext(self.file_path.name)
            format_map = {
                ".pdf": "pdf",
                ".xlsx": "xlsx",
                ".csv": "csv",
                ".json": "json",
            }
            self.file_format = format_map.get(ext.lower(), "")

    def generate_report_name(self):
        """Auto-generate descriptive report name."""
        if self.report_name:
            return self.report_name
        
        name_parts = []
        
        # Add type
        name_parts.append(self.get_report_type_display())
        
        # Add entity
        if self.manager:
            name_parts.append(f"({self.manager.get_full_name()})")
        elif self.department:
            name_parts.append(f"({self.department.name})")
        elif self.employee:
            emp_name = f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            name_parts.append(f"({emp_name})")
        
        # Add period
        name_parts.append(f"- {self.period_display}")
        
        # Add version if > 1
        if self.version > 1:
            name_parts.append(f"(v{self.version})")
        
        return " ".join(name_parts)

    def get_payload_summary(self):
        """Return summarized KPIs from payload."""
        records = self.payload.get("records", [])
        summary = self.payload.get("summary", {})
        
        if not records and not summary:
            return {
                "count": 0,
                "avg_score": 0,
                "top_performer": None,
                "weak_performer": None,
            }
        
        # Extract from summary if available
        if summary:
            return {
                "count": summary.get("total_records", len(records)),
                "avg_score": summary.get("average_score", 0),
                "top_performer": summary.get("top_performer"),
                "weak_performer": summary.get("weak_performer"),
            }
        
        # Calculate from records
        if records:
            scores = [r.get("average_score", 0) for r in records]
            avg_score = sum(scores) / len(scores) if scores else 0
            top = max(records, key=lambda r: r.get("average_score", 0), default={})
            weak = min(records, key=lambda r: r.get("average_score", 0), default={})
            
            return {
                "count": len(records),
                "avg_score": round(avg_score, 2),
                "top_performer": top.get("employee_name") or top.get("employee_full_name"),
                "weak_performer": weak.get("employee_name") or weak.get("employee_full_name"),
            }
        
        return {"count": 0, "avg_score": 0, "top_performer": None, "weak_performer": None}

    def generate_filename(self, extension=None):
        """Generate clean, unique filename for exports."""
        if extension is None:
            extension = self.file_format or "csv"
        
        # Build filename
        parts = [self.report_type.title()]
        
        if self.manager:
            parts.append(self.manager.username)
        elif self.department:
            parts.append(self.department.code)
        elif self.employee:
            parts.append(self.employee.user.emp_id)
        
        parts.append(self.period_display.replace(" ", "_"))
        parts.append(timezone.now().strftime("%Y%m%d_%H%M%S"))
        
        filename = "_".join(parts).replace(" ", "_").replace(",", "")
        return f"{filename}.{extension}"

    def record_access(self):
        """Record that report was accessed."""
        self.access_count += 1
        self.last_accessed_at = timezone.now()
        self.save(update_fields=["access_count", "last_accessed_at"])

    def soft_delete(self):
        """Soft delete (archive) report."""
        self.is_active = False
        self.save(update_fields=["is_active"])
        logger.info(f"Report archived: {self.pk} - {self.report_name}")

    def restore(self):
        """Restore archived report."""
        self.is_active = True
        self.save(update_fields=["is_active"])
        logger.info(f"Report restored: {self.pk} - {self.report_name}")

    def increment_version(self):
        """Increment version number for regeneration."""
        self.version += 1
        self.generated_at = timezone.now()

    # -----------------------------------------------------------
    # Class Methods
    # -----------------------------------------------------------
    @classmethod
    def get_latest(cls, report_type, **filters):
        """Fetch most recent active report of a given type."""
        queryset = cls.objects.filter(
            report_type=report_type,
            is_active=True,
            **filters
        )
        return queryset.order_by("-generated_at").first()

    @classmethod
    def get_or_create_report(cls, report_type, year, **kwargs):
        """Get existing report or create new one."""
        filters = {
            "report_type": report_type,
            "year": year,
            "is_active": True,
        }
        filters.update(kwargs)
        
        report = cls.objects.filter(**filters).first()
        if not report:
            report = cls.objects.create(report_type=report_type, year=year, **kwargs)
            logger.info(f"New report created: {report.report_scope}")
        
        return report

    @classmethod
    def cleanup_expired(cls):
        """Remove expired reports."""
        expired = cls.objects.filter(
            expires_at__lte=timezone.now(),
            is_active=True
        )
        count = expired.count()
        
        for report in expired:
            report.soft_delete()
        
        logger.info(f"Cleaned up {count} expired reports")
        return count

    @classmethod
    def cleanup_old_versions(cls, keep_latest=3):
        """Keep only latest N versions of each report type."""
        from django.db.models import Max
        
        # Group by report configuration
        reports = cls.objects.filter(is_active=True).values(
            "report_type", "year", "week_number", "month", "quarter",
            "manager", "department", "employee"
        ).annotate(max_version=Max("version"))
        
        deleted_count = 0
        for config in reports:
            max_ver = config.pop("max_version")
            threshold = max_ver - keep_latest
            
            if threshold > 0:
                old_versions = cls.objects.filter(
                    **config,
                    version__lte=threshold,
                    is_active=True
                )
                
                for report in old_versions:
                    report.soft_delete()
                    deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old report versions")
        return deleted_count

    # -----------------------------------------------------------
    # Save Override
    # -----------------------------------------------------------
    def save(self, *args, **kwargs):
        """Validate, calculate hash, update metadata before saving."""
        self.full_clean()
        
        # Generate report name if not set
        if not self.report_name:
            self.report_name = self.generate_report_name()
        
        # Calculate payload hash
        if self.payload:
            self.report_hash = self.calculate_hash()
        
        # Update file info if file attached
        if self.file_path:
            self.update_file_info()
        
        # Extract statistics from payload
        summary = self.get_payload_summary()
        self.record_count = summary["count"]
        self.average_score = summary["avg_score"]
        
        # Cleanup old file if replacing
        if self.pk:
            try:
                old = CachedReport.objects.get(pk=self.pk)
                if old.file_path and old.file_path != self.file_path:
                    if os.path.isfile(old.file_path.path):
                        os.remove(old.file_path.path)
                        logger.debug(f"Removed old file: {old.file_path.path}")
            except (CachedReport.DoesNotExist, OSError) as e:
                logger.warning(f"Could not remove old file: {e}")
        
        super().save(*args, **kwargs)
        logger.debug(f"Report saved: {self.pk} - {self.report_name}")

    # -----------------------------------------------------------
    # String Representation
    # -----------------------------------------------------------
    def __str__(self):
        return self.report_name or self.report_scope

    def __repr__(self):
        return (
            f"<CachedReport: {self.pk} | {self.report_type} | "
            f"{self.period_display} | v{self.version}>"
        )