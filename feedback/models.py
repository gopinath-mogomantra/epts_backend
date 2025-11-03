# ===========================================================
# feedback/models.py
# ===========================================================
"""
Enhanced feedback models with comprehensive features:
- Priority and status tracking
- Response/acknowledgment workflow
- Sentiment analysis support
- Action items tracking
- Notification integration
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q, Avg, Count
import logging

logger = logging.getLogger(__name__)

User = settings.AUTH_USER_MODEL

# -----------------------------------------------------------
# Constants
# -----------------------------------------------------------
RATING_MIN = 1
RATING_MAX = 10


# ===========================================================
# Custom QuerySet and Manager
# ===========================================================
class FeedbackQuerySet(models.QuerySet):
    """Custom queryset for feedback filtering."""
    
    def for_employee(self, employee):
        """Filter feedback for specific employee."""
        return self.filter(employee=employee)
    
    def public(self):
        """Filter public feedback."""
        return self.filter(visibility='Public')
    
    def private(self):
        """Filter private feedback."""
        return self.filter(visibility='Private')
    
    def by_rating_range(self, min_rating, max_rating):
        """Filter by rating range."""
        return self.filter(rating__gte=min_rating, rating__lte=max_rating)
    
    def positive(self):
        """High ratings (8-10)."""
        return self.filter(rating__gte=8)
    
    def neutral(self):
        """Medium ratings (5-7)."""
        return self.filter(rating__gte=5, rating__lt=8)
    
    def negative(self):
        """Low ratings (1-4)."""
        return self.filter(rating__lt=5)
    
    def unacknowledged(self):
        """Feedback not yet acknowledged by employee."""
        return self.filter(acknowledged=False)
    
    def requires_action(self):
        """Feedback marked as requiring action."""
        return self.filter(requires_action=True, action_completed=False)
    
    def by_date_range(self, start_date, end_date):
        """Filter by date range."""
        return self.filter(feedback_date__gte=start_date, feedback_date__lte=end_date)


class FeedbackManager(models.Manager):
    """Custom manager with helper methods."""
    
    def get_queryset(self):
        return FeedbackQuerySet(self.model, using=self._db)
    
    def for_employee(self, employee):
        return self.get_queryset().for_employee(employee)
    
    def public(self):
        return self.get_queryset().public()
    
    def positive(self):
        return self.get_queryset().positive()
    
    def neutral(self):
        return self.get_queryset().neutral()
    
    def negative(self):
        return self.get_queryset().negative()
    
    def get_statistics(self, employee=None, date_from=None, date_to=None):
        """Get feedback statistics."""
        qs = self.get_queryset()
        
        if employee:
            qs = qs.filter(employee=employee)
        
        if date_from:
            qs = qs.filter(feedback_date__gte=date_from)
        
        if date_to:
            qs = qs.filter(feedback_date__lte=date_to)
        
        stats = qs.aggregate(
            total=Count('id'),
            average_rating=Avg('rating'),
            positive=Count('id', filter=Q(rating__gte=8)),
            neutral=Count('id', filter=Q(rating__gte=5, rating__lt=8)),
            negative=Count('id', filter=Q(rating__lt=5)),
        )
        
        return stats


# ===========================================================
# Abstract Base Class — Enhanced for All Feedback Types
# ===========================================================
class BaseFeedback(models.Model):
    """
    Enhanced base class for all feedback categories.
    
    New features:
    - Priority levels
    - Status tracking
    - Acknowledgment workflow
    - Action items
    - Sentiment analysis
    - Tags for categorization
    """

    # =======================================================
    # Priority Choices
    # =======================================================
    PRIORITY_LOW = 'low'
    PRIORITY_NORMAL = 'normal'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'
    
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_NORMAL, 'Normal'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]
    
    # =======================================================
    # Status Choices
    # =======================================================
    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'
    STATUS_ACKNOWLEDGED = 'acknowledged'
    STATUS_ACTIONED = 'actioned'
    STATUS_ARCHIVED = 'archived'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_ACKNOWLEDGED, 'Acknowledged'),
        (STATUS_ACTIONED, 'Action Taken'),
        (STATUS_ARCHIVED, 'Archived'),
    ]
    
    # =======================================================
    # Sentiment Choices
    # =======================================================
    SENTIMENT_POSITIVE = 'positive'
    SENTIMENT_NEUTRAL = 'neutral'
    SENTIMENT_NEGATIVE = 'negative'
    SENTIMENT_MIXED = 'mixed'
    
    SENTIMENT_CHOICES = [
        (SENTIMENT_POSITIVE, 'Positive'),
        (SENTIMENT_NEUTRAL, 'Neutral'),
        (SENTIMENT_NEGATIVE, 'Negative'),
        (SENTIMENT_MIXED, 'Mixed'),
    ]

    # =======================================================
    # Core Fields
    # =======================================================
    employee = models.ForeignKey(
        "employee.Employee",
        on_delete=models.CASCADE,
        related_name="%(class)s_feedbacks",
        db_index=True,
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

    feedback_text = models.TextField(
        help_text="Detailed feedback or comments."
    )
    
    remarks = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes or context."
    )
    
    rating = models.PositiveSmallIntegerField(
        default=5,
        help_text=f"Numeric rating (scale: {RATING_MIN}–{RATING_MAX})."
    )

    # =======================================================
    # Enhanced Fields
    # =======================================================
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_NORMAL,
        db_index=True,
        help_text="Priority level of this feedback.",
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
        help_text="Current status of feedback.",
    )
    
    sentiment = models.CharField(
        max_length=10,
        choices=SENTIMENT_CHOICES,
        null=True,
        blank=True,
        help_text="Detected sentiment (can be auto-filled by AI).",
    )
    
    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tags (e.g., 'communication, teamwork').",
    )

    # =======================================================
    # Acknowledgment & Response
    # =======================================================
    acknowledged = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Has the employee acknowledged this feedback?",
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the feedback was acknowledged.",
    )
    
    employee_response = models.TextField(
        blank=True,
        null=True,
        help_text="Employee's response to the feedback.",
    )
    
    response_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When employee responded.",
    )

    # =======================================================
    # Action Items
    # =======================================================
    requires_action = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Does this feedback require follow-up action?",
    )
    
    action_items = models.TextField(
        blank=True,
        null=True,
        help_text="Specific action items to address.",
    )
    
    action_completed = models.BooleanField(
        default=False,
        help_text="Have the action items been completed?",
    )
    
    action_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When actions were completed.",
    )

    # =======================================================
    # Visibility & Access
    # =======================================================
    visibility = models.CharField(
        max_length=20,
        choices=[("Private", "Private"), ("Public", "Public")],
        default="Private",
        db_index=True,
        help_text="Defines whether feedback is visible in employee dashboards.",
    )
    
    confidential = models.BooleanField(
        default=False,
        help_text="Mark as highly confidential (restricted access).",
    )

    # =======================================================
    # Creator & Metadata
    # =======================================================
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        help_text="User who submitted this feedback.",
    )

    source_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        editable=False,
        help_text="Auto-filled feedback source type.",
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured data.",
    )

    # =======================================================
    # Timestamps
    # =======================================================
    feedback_date = models.DateField(
        default=timezone.localdate,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # =======================================================
    # Manager
    # =======================================================
    objects = FeedbackManager()

    # =======================================================
    # Meta Info
    # =======================================================
    class Meta:
        abstract = True
        ordering = ["-priority", "-feedback_date", "-created_at"]
        indexes = [
            models.Index(fields=["employee", "feedback_date"], name="%(class)s_emp_date_idx"),
            models.Index(fields=["employee", "status"], name="%(class)s_emp_status_idx"),
            models.Index(fields=["priority", "status"], name="%(class)s_priority_idx"),
            models.Index(fields=["acknowledged"], name="%(class)s_ack_idx"),
        ]

    # =======================================================
    # Properties
    # =======================================================
    @property
    def is_positive(self):
        """Check if feedback is positive (rating >= 8)."""
        return self.rating >= 8
    
    @property
    def is_negative(self):
        """Check if feedback is negative (rating < 5)."""
        return self.rating < 5
    
    @property
    def is_urgent(self):
        """Check if feedback is urgent priority."""
        return self.priority == self.PRIORITY_URGENT
    
    @property
    def needs_attention(self):
        """Check if feedback needs immediate attention."""
        return (
            self.is_urgent or 
            (self.is_negative and not self.acknowledged) or
            (self.requires_action and not self.action_completed)
        )

    # =======================================================
    # Validation
    # =======================================================
    def clean(self):
        """Validate feedback data."""
        super().clean()
        
        # Validate rating range
        if self.rating is not None and not (RATING_MIN <= self.rating <= RATING_MAX):
            raise ValidationError({
                'rating': f"Rating must be between {RATING_MIN} and {RATING_MAX}."
            })

        # Validate department matches employee
        if self.employee and self.department:
            emp_dept = getattr(self.employee, "department", None)
            if emp_dept and self.department != emp_dept:
                raise ValidationError({
                    'department': "Department mismatch with employee's assigned department."
                })
        
        # Validate acknowledgment logic
        if self.acknowledged and not self.acknowledged_at:
            self.acknowledged_at = timezone.now()
        
        # Auto-determine sentiment based on rating if not set
        if not self.sentiment:
            if self.rating >= 8:
                self.sentiment = self.SENTIMENT_POSITIVE
            elif self.rating >= 5:
                self.sentiment = self.SENTIMENT_NEUTRAL
            else:
                self.sentiment = self.SENTIMENT_NEGATIVE

    # =======================================================
    # Save Override
    # =======================================================
    def save(self, *args, **kwargs):
        """Auto-fill department, source type, and trigger notifications."""
        # Auto-fill department from employee
        if self.employee and not self.department:
            self.department = self.employee.department

        # Auto-fill source type
        if not self.source_type:
            self.source_type = self.__class__.__name__.replace("Feedback", "")

        # Run validation
        self.full_clean()
        
        # Track if this is a new record
        is_new = self.pk is None
        
        super().save(*args, **kwargs)

        # Send notification for new feedback
        if is_new:
            self._send_feedback_notification()

    def _send_feedback_notification(self):
        """Send notification when feedback is created."""
        try:
            from notifications.models import Notification
            from notifications.signals import feedback_received
            
            if self.employee and hasattr(self.employee, "user"):
                # Determine priority based on feedback rating and priority
                if self.priority == self.PRIORITY_URGENT:
                    notif_priority = Notification.PRIORITY_URGENT
                elif self.priority == self.PRIORITY_HIGH or self.is_negative:
                    notif_priority = Notification.PRIORITY_HIGH
                else:
                    notif_priority = Notification.PRIORITY_MEDIUM
                
                # Create notification
                message = (
                    f"New {self.source_type} feedback received "
                    f"(Rating: {self.rating}/10)"
                )
                
                if self.requires_action:
                    message += " - Action required"
                
                Notification.objects.create(
                    employee=self.employee.user,
                    message=message,
                    category=Notification.CATEGORY_FEEDBACK,
                    priority=notif_priority,
                    link=f"/feedback/{self.source_type.lower()}/{self.id}/",
                    auto_delete=False,
                    metadata={
                        'feedback_id': self.id,
                        'feedback_type': self.source_type,
                        'rating': self.rating,
                        'requires_action': self.requires_action,
                    }
                )
                
                # Send signal for custom handlers
                feedback_received.send(
                    sender=self.__class__,
                    employee=self.employee.user,
                    feedback=self,
                    from_user=self.created_by
                )
                
                logger.info(
                    f"Notification sent for {self.source_type} feedback "
                    f"to {self.employee.user.username}"
                )
        except Exception as e:
            logger.error(f"Failed to send feedback notification: {e}")

    # =======================================================
    # Utility Methods
    # =======================================================
    def acknowledge(self, response=None):
        """Mark feedback as acknowledged by employee."""
        self.acknowledged = True
        self.acknowledged_at = timezone.now()
        self.status = self.STATUS_ACKNOWLEDGED
        
        if response:
            self.employee_response = response
            self.response_date = timezone.now()
        
        self.save(update_fields=[
            'acknowledged', 'acknowledged_at', 'status', 
            'employee_response', 'response_date'
        ])
        
        logger.info(f"Feedback {self.id} acknowledged by employee")
    
    def complete_action(self):
        """Mark action items as completed."""
        if not self.requires_action:
            raise ValidationError("This feedback does not require action.")
        
        self.action_completed = True
        self.action_completed_at = timezone.now()
        self.status = self.STATUS_ACTIONED
        
        self.save(update_fields=[
            'action_completed', 'action_completed_at', 'status'
        ])
        
        logger.info(f"Action items completed for feedback {self.id}")
    
    def archive(self):
        """Archive this feedback."""
        self.status = self.STATUS_ARCHIVED
        self.save(update_fields=['status'])
        
        logger.info(f"Feedback {self.id} archived")

    # =======================================================
    # String Representation
    # =======================================================
    def __str__(self):
        emp_name = (
            f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
            if self.employee and hasattr(self.employee, "user")
            else "Unknown Employee"
        )
        
        priority_icon = {
            self.PRIORITY_URGENT: "🔴",
            self.PRIORITY_HIGH: "🟠",
            self.PRIORITY_NORMAL: "🟡",
            self.PRIORITY_LOW: "🔵",
        }.get(self.priority, "⚪")
        
        return f"{priority_icon} {self.__class__.__name__} → {emp_name} ({self.rating}/10)"

    def get_feedback_summary(self):
        """Compact JSON summary for dashboards and analytics."""
        return {
            "id": self.id,
            "emp_id": getattr(self.employee.user, "emp_id", None),
            "employee_name": (
                f"{self.employee.user.first_name} {self.employee.user.last_name}".strip()
                if self.employee and hasattr(self.employee, "user")
                else None
            ),
            "department_name": getattr(self.department, "name", "-"),
            "rating": self.rating,
            "priority": self.priority,
            "status": self.status,
            "sentiment": self.sentiment,
            "visibility": self.visibility,
            "acknowledged": self.acknowledged,
            "requires_action": self.requires_action,
            "feedback_date": self.feedback_date.isoformat(),
            "submitted_by": getattr(self.created_by, "username", "-"),
            "source_type": self.source_type,
        }


# ===========================================================
# Concrete Feedback Models
# ===========================================================
class GeneralFeedback(BaseFeedback):
    """General feedback from Admins or HR (non-managerial)."""

    feedback_category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Category of general feedback (e.g., 'HR Review', 'Performance Check').",
    )

    class Meta:
        verbose_name = "General Feedback"
        verbose_name_plural = "General Feedback"
        db_table = "feedback_general"


class ManagerFeedback(BaseFeedback):
    """Manager's feedback on an employee's performance."""

    manager_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Auto-filled with Manager's name if available.",
    )
    
    one_on_one_session = models.BooleanField(
        default=False,
        help_text="Was this feedback given during a 1:1 session?",
    )
    
    improvement_areas = models.TextField(
        blank=True,
        null=True,
        help_text="Specific areas for improvement.",
    )
    
    strengths = models.TextField(
        blank=True,
        null=True,
        help_text="Employee's key strengths.",
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
        db_table = "feedback_manager"


class ClientFeedback(BaseFeedback):
    """Client feedback for employee or project delivery."""

    client_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Client's name or organization.",
    )
    
    project_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Associated project name.",
    )
    
    would_recommend = models.BooleanField(
        default=True,
        help_text="Would the client recommend this employee?",
    )

    def save(self, *args, **kwargs):
        if not self.client_name:
            self.client_name = "Anonymous Client"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Client Feedback"
        verbose_name_plural = "Client Feedback"
        db_table = "feedback_client"