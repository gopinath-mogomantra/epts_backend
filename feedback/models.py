from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


# ===========================================================
# ✅ Constants
# ===========================================================
RATING_MIN = 1
RATING_MAX = 10


# ===========================================================
# ✅ Abstract Base Class for Feedback
# ===========================================================
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
    rating = models.PositiveSmallIntegerField(default=0, help_text=f"Numeric rating ({RATING_MIN}–{RATING_MAX} scale).")

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
        help_text="Defines whether feedback is visible in dashboards/reports.",
    )

    feedback_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --------------------------------------------------------
    # 🧩 Optional Analytics Field
    # --------------------------------------------------------
    source_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        editable=False,
        help_text="Auto-filled field (Admin / Manager / Client) for analytics grouping.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]
        index_together = [("employee", "department", "feedback_date")]

    # --------------------------------------------------------
    # ✅ Display & Utility
    # --------------------------------------------------------
    def __str__(self):
        emp_name = (
            f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if self.employee and hasattr(self.employee, "user")
            else "Unknown Employee"
        )
        return f"{self.__class__.__name__} → {emp_name} (Rating: {self.rating}/10)"

    def get_feedback_summary(self):
        """Return short summary for API or dashboards."""
        return {
            "employee": getattr(self.employee.user, "emp_id", None),
            "rating": self.rating,
            "visibility": self.visibility,
            "feedback_date": self.feedback_date,
            "department": getattr(self.department, "name", "-"),
            "created_by": getattr(self.created_by, "username", "-"),
        }

    # --------------------------------------------------------
    # ✅ Validation & Save Logic
    # --------------------------------------------------------
    def clean(self):
        """Validate rating and department consistency."""
        if self.rating is not None and not (RATING_MIN <= self.rating <= RATING_MAX):
            raise ValidationError({"rating": f"Rating must be between {RATING_MIN} and {RATING_MAX}."})

        if self.employee and self.department:
            if self.employee.department and self.department != self.employee.department:
                raise ValidationError({"department": "Department does not match the employee’s assigned department."})

    def save(self, *args, **kwargs):
        """Auto-fill department, source_type, and trigger optional notification."""
        if self.employee and not self.department:
            self.department = self.employee.department

        # Auto-derive source type
        if not self.source_type:
            self.source_type = self.__class__.__name__.replace("Feedback", "")

        self.full_clean()
        super().save(*args, **kwargs)

        # ----------------------------------------------
        # Optional Notification Trigger
        # ----------------------------------------------
        try:
            from notifications.models import Notification
            if hasattr(self.employee, "user"):
                Notification.objects.create(
                    employee=self.employee.user,
                    message=(
                        f"📢 New {self.source_type} feedback received "
                        f"on {self.feedback_date.strftime('%d %b %Y')} "
                        f"(Rating: {self.rating}/10)."
                    ),
                    auto_delete=True,
                )
        except Exception:
            # Fail silently if Notification model unavailable
            pass


# ===========================================================
# ✅ Concrete Feedback Models
# ===========================================================
class GeneralFeedback(BaseFeedback):
    """General feedback (usually from Admins or HR staff)."""

    class Meta:
        verbose_name = "General Feedback"
        verbose_name_plural = "General Feedbacks"


class ManagerFeedback(BaseFeedback):
    """Feedback given by a manager about an employee’s performance."""
    manager_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Manager's name (auto-filled if available).",
    )

    def save(self, *args, **kwargs):
        # Auto-fill manager_name if empty
        if not self.manager_name and self.created_by:
            self.manager_name = f"{getattr(self.created_by, 'first_name', '')} {getattr(self.created_by, 'last_name', '')}".strip()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Manager Feedback"
        verbose_name_plural = "Manager Feedbacks"


class ClientFeedback(BaseFeedback):
    """Feedback provided by clients regarding project quality, delivery, or support."""
    client_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Client's name or organization giving the feedback.",
    )

    def save(self, *args, **kwargs):
        # Default to 'Anonymous Client' if no name
        if not self.client_name:
            self.client_name = "Anonymous Client"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Client Feedback"
        verbose_name_plural = "Client Feedbacks"
