# ===============================================
# feedback/models.py (Final Synced Version)
# ===============================================

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


# ============================================================
# ✅ Abstract Base Class for Feedback
# ============================================================
class BaseFeedback(models.Model):
    """
    Abstract base model for all feedback types.
    Used by GeneralFeedback, ManagerFeedback, and ClientFeedback.
    """

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
        help_text="Department of the employee.",
    )

    feedback_text = models.TextField(help_text="Detailed feedback or comments from the reviewer.")
    remarks = models.TextField(blank=True, null=True, help_text="Additional notes or suggestions.")

    rating = models.PositiveSmallIntegerField(
        default=0,
        help_text="Numeric rating (1–10 scale).",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        help_text="User who submitted this feedback.",
    )

    visibility = models.CharField(
        max_length=20,
        choices=[("Private", "Private"), ("Public", "Public")],
        default="Private",
        help_text="Defines whether the feedback is public or private in dashboards/reports.",
    )

    feedback_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --------------------------------------------------------
    # Meta & Display
    # --------------------------------------------------------
    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        emp_name = (
            f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if self.employee and hasattr(self.employee, "user")
            else "Unknown Employee"
        )
        return f"{self.__class__.__name__} → {emp_name} (Rating: {self.rating}/10)"

    # --------------------------------------------------------
    # Validation & Save Logic
    # --------------------------------------------------------
    def clean(self):
        """Validate rating and department consistency."""
        if self.rating is not None and not (1 <= self.rating <= 10):
            raise ValidationError("Rating must be between 1 and 10.")
        if self.employee and self.department:
            if self.employee.department and self.department != self.employee.department:
                raise ValidationError(
                    {"department": "Department does not match the employee’s assigned department."}
                )

    def save(self, *args, **kwargs):
        """Auto-fill department if missing and trigger notifications."""
        if self.employee and not self.department:
            self.department = self.employee.department
        self.full_clean()
        super().save(*args, **kwargs)

        # ----------------------------------------------
        # Optional Notification (if notifications app installed)
        # ----------------------------------------------
        try:
            from notifications.models import Notification
            Notification.objects.create(
                employee=self.employee.user,
                message=f"New {self.__class__.__name__.replace('Feedback', '').strip()} feedback received "
                        f"on {self.feedback_date.strftime('%d %b %Y')} (Rating: {self.rating}/10).",
                auto_delete=True,
            )
        except Exception:
            # Fail silently if notifications app not ready
            pass


# ============================================================
# ✅ Concrete Feedback Models
# ============================================================
class GeneralFeedback(BaseFeedback):
    """
    General feedback typically given by Admins or HR staff.
    Covers attitude, teamwork, and overall workplace behavior.
    """

    class Meta:
        verbose_name = "General Feedback"
        verbose_name_plural = "General Feedbacks"


class ManagerFeedback(BaseFeedback):
    """
    Feedback given by a manager about an employee’s performance.
    """
    manager_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Manager's name (auto-filled or entered manually).",
    )

    class Meta:
        verbose_name = "Manager Feedback"
        verbose_name_plural = "Manager Feedbacks"


class ClientFeedback(BaseFeedback):
    """
    Feedback provided by clients regarding project quality, delivery, or support.
    """
    client_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Client's name or organization giving the feedback.",
    )

    class Meta:
        verbose_name = "Client Feedback"
        verbose_name_plural = "Client Feedbacks"
