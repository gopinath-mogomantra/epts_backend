# feedback/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError


User = settings.AUTH_USER_MODEL


class BaseFeedback(models.Model):
    """
    Abstract base model for all feedback types.
    Common fields shared by General, Manager, and Client feedback.
    """

    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="%(class)s_feedbacks",
        help_text="Employee receiving this feedback",
    )

    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_feedbacks",
        help_text="Employee's department",
    )

    feedback_text = models.TextField(help_text="Detailed feedback or comments")

    remarks = models.TextField(
        blank=True,
        null=True,
        help_text="Additional remarks or notes by the reviewer",
    )

    rating = models.PositiveSmallIntegerField(
        default=0,
        help_text="Numeric rating between 1 and 10",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        help_text="User who submitted this feedback",
    )

    visibility = models.CharField(
        max_length=20,
        choices=[("Private", "Private"), ("Public", "Public")],
        default="Private",
        help_text="Determines who can view this feedback in reports or dashboards",
    )

    feedback_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        emp_name = (
            f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if self.employee and hasattr(self.employee, "user")
            else "Unknown Employee"
        )
        return f"{self.__class__.__name__} for {emp_name} (Rating: {self.rating})"

    def clean(self):
        """Ensure rating is between 1–10."""
        if self.rating is None:
            return
        if not (1 <= self.rating <= 10):
            raise ValidationError("Rating must be between 1 and 10.")


# ---------------------------------------------------------
# Concrete Feedback Models
# ---------------------------------------------------------

class GeneralFeedback(BaseFeedback):
    """
    General feedback given by Admin or HR department.
    Typically covers attitude, behavior, and overall performance.
    """

    class Meta:
        verbose_name = "General Feedback"
        verbose_name_plural = "General Feedbacks"


class ManagerFeedback(BaseFeedback):
    """
    Feedback provided by a Manager about an employee’s work performance.
    Includes optional manager_name for reference.
    """
    manager_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Name of the manager providing the feedback",
    )

    class Meta:
        verbose_name = "Manager Feedback"
        verbose_name_plural = "Manager Feedbacks"


class ClientFeedback(BaseFeedback):
    """
    Feedback provided by a client regarding project delivery or quality.
    Includes optional client_name for audit tracking.
    """
    client_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Name of the client providing the feedback",
    )

    class Meta:
        verbose_name = "Client Feedback"
        verbose_name_plural = "Client Feedbacks"
