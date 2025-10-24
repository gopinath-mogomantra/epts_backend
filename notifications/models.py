# ===============================================
# notifications/models.py  (Final Updated Version)
# ===============================================

from django.db import models
from django.conf import settings
from django.utils import timezone


class Notification(models.Model):
    """
    Stores system-generated notifications for employees.
    Notifications can be:
    - Temporary (auto-deleted after reading)
    - Persistent (kept and marked as read)
    """

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="User who will receive this notification.",
    )

    message = models.CharField(
        max_length=255,
        help_text="Short notification message or description.",
    )

    is_read = models.BooleanField(
        default=False,
        help_text="Indicates if the notification has been read.",
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the notification was read.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this notification was created.",
    )

    auto_delete = models.BooleanField(
        default=True,
        help_text="If True → delete automatically after being read. "
                  "If False → keep record marked as read.",
    )

    # Optional: allow department-level notifications in future
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Optional: department-wide notification scope.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["employee", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    # ------------------------------------------------------
    # Instance Methods
    # ------------------------------------------------------
    def mark_as_read(self, auto_commit=True):
        """
        Marks the notification as read.
        Deletes it immediately if `auto_delete=True`.
        """
        self.is_read = True
        self.read_at = timezone.now()
        if auto_commit:
            self.save(update_fields=["is_read", "read_at"])

        # Auto-delete if flagged
        if self.auto_delete:
            self.delete()

    def mark_as_unread(self):
        """Reverts a notification back to unread state."""
        self.is_read = False
        self.read_at = None
        self.save(update_fields=["is_read", "read_at"])

    def __str__(self):
        """Readable admin display."""
        status = "✅ Read" if self.is_read else "🕐 Unread"
        return f"[{status}] {self.employee} - {self.message[:60]}"
