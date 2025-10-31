# ===========================================================
# feedback/models.py
# ===========================================================
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL

# -----------------------------------------------------------
# Constants
# -----------------------------------------------------------
RATING_MIN = 1
RATING_MAX = 10


# ===========================================================
# Abstract Base Class — Common for All Feedback Types
# ===========================================================
class BaseFeedback(models.Model):
    """
    Common fields for all feedback categories (Admin, Manager, Client).
    """

    # -------------------------------------------------------
    # Core Fields
    # -------------------------------------------------------
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="%(class)s_feedbacks",
        help_text="Employee receiving this feedback.",
    )

    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_feedbacks",
        help_text="Department under which the feedback is recorded.",
    )

    feedback_text = models.TextField(help_text="Detailed feedback or comments.")
    remarks = models.TextField(blank=True, null=True, help_text="Additional notes or context.")
    rating = models.PositiveSmallIntegerField(
        default=0,
        help_text=f"Numeric rating (scale: {RATING_MIN}–{RATING_MAX})."
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        help_text="User who submitted this feedback (Admin / Manager / Client).",
    )

    visibility = models.CharField(
        max_length=20,
        choices=[("Private", "Private"), ("Public", "Public")],
        default="Private",
        help_text="Defines whether feedback is visible in employee dashboards.",
    )

    feedback_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    source_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        editable=False,
        help_text="Auto-filled (Admin / Manager / Client) for analytics grouping.",
    )

    # -------------------------------------------------------
    # Meta Info
    # -------------------------------------------------------
    class Meta:
        abstract = True
        ordering = ["-feedback_date", "-created_at"]
        indexes = [
            models.Index(fields=["employee", "department", "feedback_date"]),
        ]

    # -------------------------------------------------------
    # Validation
    # -------------------------------------------------------
    def clean(self):
        """Ensure rating is within valid range and department matches employee."""
        if self.rating is not None and not (RATING_MIN <= self.rating <= RATING_MAX):
            raise ValidationError({"rating": f"Rating must be between {RATING_MIN} and {RATING_MAX}."})

        if self.employee and self.department:
            emp_dept = getattr(self.employee, "department", None)
            if emp_dept and self.department != emp_dept:
                raise ValidationError({"department": "Department mismatch with employee’s assigned department."})

    # -------------------------------------------------------
    # Save Override
    # -------------------------------------------------------
    def save(self, *args, **kwargs):
        """Auto-fill department, source type, and trigger notification."""
        if self.employee and not self.department:
            self.department = self.employee.department

        if not self.source_type:
            self.source_type = self.__class__.__name__.replace("Feedback", "")

        self.full_clean()
        super().save(*args, **kwargs)

        # Trigger notification (optional)
        try:
            from notifications.models import Notification
            if hasattr(self.employee, "user"):
                Notification.objects.create(
                    employee=self.employee.user,
                    message=(
                        f"New {self.source_type} feedback received on "
                        f"{self.feedback_date.strftime('%d %b %Y')} "
                        f"(Rating: {self.rating}/10)."
                    ),
                    auto_delete=True,
                )
        except Exception:
            pass  # Fail silently if Notification model missing

    # -------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------
    def __str__(self):
        emp_name = (
            f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if self.employee and hasattr(self.employee, "user")
            else "Unknown Employee"
        )
        return f"{self.__class__.__name__} → {emp_name} ({self.rating}/10)"

    def get_feedback_summary(self):
        """Compact JSON summary for dashboards and analytics."""
        return {
            "emp_id": getattr(self.employee.user, "emp_id", None),
            "department_name": getattr(self.department, "name", "-"),
            "rating": self.rating,
            "visibility": self.visibility,
            "feedback_date": self.feedback_date,
            "submitted_by": getattr(self.created_by, "username", "-"),
            "source_type": self.source_type,
        }


# ===========================================================
# Feedback Variants
# ===========================================================
class GeneralFeedback(BaseFeedback):
    """General feedback from Admins or HR (non-managerial)."""

    class Meta:
        verbose_name = "General Feedback"
        verbose_name_plural = "General Feedback"


class ManagerFeedback(BaseFeedback):
    """Manager's feedback on an employee’s performance."""

    manager_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Auto-filled with Manager’s name if available.",
    )

    def save(self, *args, **kwargs):
        if not self.manager_name and self.created_by:
            first = getattr(self.created_by, "first_name", "")
            last = getattr(self.created_by, "last_name", "")
            self.manager_name = f"{first} {last}".strip()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Manager Feedback"
        verbose_name_plural = "Manager Feedback"


class ClientFeedback(BaseFeedback):
    """Client feedback for employee or project delivery."""

    client_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Client's name or organization.",
    )

    def save(self, *args, **kwargs):
        if not self.client_name:
            self.client_name = "Anonymous Client"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Client Feedback"
        verbose_name_plural = "Client Feedback"
