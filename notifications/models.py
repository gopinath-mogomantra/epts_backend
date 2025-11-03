# ===========================================================
# notifications/models.py 
# ===========================================================
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


class NotificationQuerySet(models.QuerySet):
    """Custom QuerySet for common notification queries."""
    
    def unread(self):
        """Filter for unread notifications."""
        return self.filter(is_read=False)
    
    def read(self):
        """Filter for read notifications."""
        return self.filter(is_read=True)
    
    def for_employee(self, employee):
        """Filter notifications for specific employee."""
        return self.filter(employee=employee)
    
    def by_priority(self, priority):
        """Filter by priority level."""
        return self.filter(priority=priority)
    
    def not_expired(self):
        """Filter out expired notifications."""
        now = timezone.now()
        return self.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    
    def expired(self):
        """Get expired notifications."""
        return self.filter(expires_at__lte=timezone.now())
    
    def by_category(self, category):
        """Filter by category."""
        return self.filter(category=category)


class NotificationManager(models.Manager):
    """Custom manager with helper methods for notifications."""
    
    def get_queryset(self):
        return NotificationQuerySet(self.model, using=self._db)
    
    def unread(self):
        return self.get_queryset().unread()
    
    def read(self):
        return self.get_queryset().read()
    
    def for_employee(self, employee):
        return self.get_queryset().for_employee(employee)
    
    def not_expired(self):
        return self.get_queryset().not_expired()
    
    def create_for_employee(self, employee, message, **kwargs):
        """
        Create a notification for a specific employee.
        
        Args:
            employee: User instance
            message: Notification message
            **kwargs: Additional notification fields
        
        Returns:
            Notification instance
        """
        return self.create(employee=employee, message=message, **kwargs)
    
    def create_for_department(self, department, message, **kwargs):
        """
        Create notifications for all employees in a department.
        
        Args:
            department: Department instance
            message: Notification message
            **kwargs: Additional notification fields
        
        Returns:
            List of created Notification instances
        """
        employees = department.employees.filter(is_active=True)
        notifications = []
        
        for employee in employees:
            notification = self.create(
                employee=employee,
                message=message,
                department=department,
                **kwargs
            )
            notifications.append(notification)
            logger.info(f"Created department notification for {employee}: {message[:50]}")
        
        return notifications
    
    def bulk_mark_read(self, employee):
        """
        Mark all unread notifications as read for an employee.
        
        Args:
            employee: User instance
        
        Returns:
            Number of notifications marked as read
        """
        notifications = self.filter(employee=employee, is_read=False)
        count = notifications.count()
        
        # Update read status
        notifications.update(is_read=True, read_at=timezone.now())
        
        # Handle auto-delete notifications
        auto_delete_notifications = notifications.filter(auto_delete=True)
        deleted_count = auto_delete_notifications.count()
        auto_delete_notifications.delete()
        
        logger.info(
            f"Marked {count} notifications as read for {employee}. "
            f"Auto-deleted {deleted_count} notifications."
        )
        
        return count
    
    def cleanup_expired(self):
        """
        Delete all expired notifications.
        
        Returns:
            Number of deleted notifications
        """
        expired = self.get_queryset().expired()
        count = expired.count()
        expired.delete()
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired notifications")
        
        return count


class Notification(models.Model):
    """
    Stores system-generated notifications for employees.
    
    Features:
    - Priority-based notifications (low, medium, high, urgent)
    - Auto-deletion after reading (configurable)
    - Persistent read records
    - Department broadcast notifications
    - Expiration support
    - Rich metadata storage
    """

    # =======================================================
    # Priority Levels
    # =======================================================
    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'
    
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
        (PRIORITY_URGENT, 'Urgent'),
    ]

    # =======================================================
    # Category Types
    # =======================================================
    CATEGORY_PERFORMANCE = 'performance'
    CATEGORY_FEEDBACK = 'feedback'
    CATEGORY_SYSTEM = 'system'
    CATEGORY_ATTENDANCE = 'attendance'
    CATEGORY_LEAVE = 'leave'
    CATEGORY_ANNOUNCEMENT = 'announcement'
    
    CATEGORY_CHOICES = [
        (CATEGORY_PERFORMANCE, 'Performance'),
        (CATEGORY_FEEDBACK, 'Feedback'),
        (CATEGORY_SYSTEM, 'System'),
        (CATEGORY_ATTENDANCE, 'Attendance'),
        (CATEGORY_LEAVE, 'Leave'),
        (CATEGORY_ANNOUNCEMENT, 'Announcement'),
    ]

    # =======================================================
    # Core Fields
    # =======================================================
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
        help_text="User who will receive this notification.",
    )

    message = models.CharField(
        max_length=255,
        help_text="Short notification message or description.",
    )

    link = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Optional URL or route link for redirection (e.g., /reports/weekly/?week=44&year=2025)",
    )

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_PERFORMANCE,
        db_index=True,
        help_text="Category of the notification",
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
        db_index=True,
        help_text="Priority level of the notification",
    )

    # =======================================================
    # Status Fields
    # =======================================================
    is_read = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Indicates whether the notification has been read.",
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the notification was marked as read.",
    )

    auto_delete = models.BooleanField(
        default=True,
        help_text="If True → delete automatically after being read. "
                  "If False → keep record marked as read.",
    )

    # =======================================================
    # Timestamp Fields
    # =======================================================
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the notification was created.",
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Optional expiration timestamp. Notification auto-expires after this time.",
    )

    # =======================================================
    # Additional Context
    # =======================================================
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Optional: department-wide notification scope.",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional structured data for the notification (action_id, reference_id, etc.)",
    )

    # =======================================================
    # Managers
    # =======================================================
    objects = NotificationManager()

    # =======================================================
    # Meta & Indexing
    # =======================================================
    class Meta:
        ordering = ["-priority", "-created_at"]  # Urgent first, then newest
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["employee", "is_read"], name="notif_emp_read_idx"),
            models.Index(fields=["employee", "-created_at"], name="notif_emp_created_idx"),
            models.Index(fields=["priority", "-created_at"], name="notif_priority_idx"),
            models.Index(fields=["category", "is_read"], name="notif_cat_read_idx"),
            models.Index(fields=["expires_at"], name="notif_expires_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(read_at__isnull=True) | Q(is_read=True),
                name="read_at_requires_is_read"
            ),
        ]

    # =======================================================
    # Validation
    # =======================================================
    def clean(self):
        """Validate notification data."""
        super().clean()
        
        # Ensure read_at is only set when is_read is True
        if self.read_at and not self.is_read:
            raise ValidationError({
                'read_at': 'read_at can only be set when is_read is True'
            })
        
        # Ensure expires_at is in the future when creating
        if self.expires_at and not self.pk:
            if self.expires_at <= timezone.now():
                raise ValidationError({
                    'expires_at': 'Expiration date must be in the future'
                })

    # =======================================================
    # Properties
    # =======================================================
    @property
    def is_expired(self):
        """Check if notification has expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def is_urgent(self):
        """Check if notification is urgent."""
        return self.priority == self.PRIORITY_URGENT
    
    @property
    def age_in_hours(self):
        """Get notification age in hours."""
        return (timezone.now() - self.created_at).total_seconds() / 3600

    # =======================================================
    # Utility Methods
    # =======================================================
    def mark_as_read(self, auto_commit=True):
        """
        Marks this notification as read and handles auto-deletion.
        
        Args:
            auto_commit: If True, saves changes immediately
        
        Note:
            If auto_delete is True, the notification will be deleted.
            This method returns before deletion occurs.
        """
        if self.is_read:
            logger.debug(f"Notification already read: {self}")
            return

        self.is_read = True
        self.read_at = timezone.now()

        if auto_commit:
            self.save(update_fields=["is_read", "read_at"])
            logger.info(f"Notification marked as read for {self.employee} at {self.read_at}")

        # Handle auto-deletion separately to avoid issues during save
        if self.auto_delete:
            logger.info(f"Auto-deleting read notification for {self.employee}: {self.message[:50]}")
            self.delete()

    def mark_as_unread(self, auto_commit=True):
        """
        Reverts a notification back to unread status.
        
        Args:
            auto_commit: If True, saves changes immediately
        
        Note:
            Primarily for admin/testing purposes.
        """
        if not self.is_read:
            logger.debug(f"Notification already unread: {self}")
            return
            
        self.is_read = False
        self.read_at = None
        
        if auto_commit:
            self.save(update_fields=["is_read", "read_at"])
            logger.info(f"Notification reverted to unread for {self.employee}")

    def soft_delete(self):
        """
        Marks notification for auto-cleanup without immediate deletion.
        """
        if self.auto_delete:
            logger.debug(f"Notification already flagged for auto-delete: {self}")
            return
            
        self.auto_delete = True
        self.save(update_fields=["auto_delete"])
        logger.info(f"Notification flagged for auto-delete: {self}")

    def extend_expiration(self, hours=24):
        """
        Extend notification expiration by specified hours.
        
        Args:
            hours: Number of hours to extend (default: 24)
        """
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=hours)
        else:
            self.expires_at += timezone.timedelta(hours=hours)
        
        self.save(update_fields=["expires_at"])
        logger.info(f"Extended expiration for notification {self.pk} by {hours} hours")

    def set_metadata(self, key, value):
        """
        Set a metadata field.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        if not isinstance(self.metadata, dict):
            self.metadata = {}
        self.metadata[key] = value
        self.save(update_fields=["metadata"])

    def get_metadata(self, key, default=None):
        """
        Get a metadata field.
        
        Args:
            key: Metadata key
            default: Default value if key not found
        
        Returns:
            Metadata value or default
        """
        if not isinstance(self.metadata, dict):
            return default
        return self.metadata.get(key, default)

    # =======================================================
    # String Representations
    # =======================================================
    def __str__(self):
        """Readable display name for admin and shell."""
        priority_icon = {
            self.PRIORITY_LOW: '🔵',
            self.PRIORITY_MEDIUM: '🟡',
            self.PRIORITY_HIGH: '🟠',
            self.PRIORITY_URGENT: '🔴',
        }.get(self.priority, '⚪')
        
        status = "✓" if self.is_read else "◯"
        
        return f"{priority_icon} [{status}] {self.employee} — {self.message[:50]}"
    
    def __repr__(self):
        """Developer-friendly representation."""
        return (
            f"<Notification id={self.pk} employee={self.employee.username} "
            f"priority={self.priority} read={self.is_read}>"
        )


# =======================================================
# Signal Handlers (Optional - create in signals.py)
# =======================================================
"""
Recommended signal handlers to add in notifications/signals.py:

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

@receiver(post_save, sender=Notification)
def invalidate_notification_cache(sender, instance, **kwargs):
    '''Invalidate cached notification count when new notification is created.'''
    cache_key = f'unread_notifications_{instance.employee.pk}'
    cache.delete(cache_key)

@receiver(post_save, sender=Notification)
def send_push_notification(sender, instance, created, **kwargs):
    '''Send push notification for urgent notifications.'''
    if created and instance.is_urgent:
        # Integration with push notification service
        pass
"""