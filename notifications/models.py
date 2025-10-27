from django.db import models
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Notification(models.Model):
    """
    Stores system-generated notifications for employees.
    Supports:
    - Auto-deletion after reading (temporary)
    - Persistent notifications (marked as read)
    - Optional department-wide targeting (for broadcast use)
    """

    # =======================================================
    # 🔹 Core Fields
    # =======================================================
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
        help_text="Indicates whether the notification has been read.",
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the notification was marked as read.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the notification was created.",
    )

    auto_delete = models.BooleanField(
        default=True,
        help_text="If True → delete automatically after being read. "
                  "If False → keep record marked as read.",
    )

    # =======================================================
    # 🔹 Optional: Departmental Notifications (Future Feature)
    # =======================================================
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Optional: department-wide notification scope.",
    )

    # =======================================================
    # 🔹 Meta Configuration
    # =======================================================
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["employee", "is_read"]),
            models.Index(fields=["created_at"]),
        ]

    # =======================================================
    # 🔹 Core Methods
    # =======================================================
    def mark_as_read(self, auto_commit=True):
        """
        Marks this notification as read.
        If auto_delete=True, deletes it immediately after marking as read.
        """
        if self.is_read:
            logger.debug(f"🔁 Notification already read: {self}")
            return

        self.is_read = True
        self.read_at = timezone.now()

        if auto_commit:
            self.save(update_fields=["is_read", "read_at"])
            logger.info(f"📬 Notification marked as read for {self.employee} at {self.read_at}")

        # Auto-delete if configured
        if self.auto_delete:
            logger.info(f"🗑️ Auto-deleting read notification for {self.employee}: {self.message[:50]}")
            self.delete()

    def mark_as_unread(self, auto_commit=True):
        """
        Reverts a notification back to unread state.
        Useful for testing, admin corrections, or UX reset.
        """
        if not self.is_read:
            logger.debug(f"🔁 Notification already unread: {self}")
            return

        self.is_read = False
        self.read_at = None

        if auto_commit:
            self.save(update_fields=["is_read", "read_at"])
            logger.info(f"🔄 Notification reverted to unread for {self.employee}")

    def soft_delete(self):
        """
        Soft delete hook — sets auto_delete flag for future auto-cleanup.
        (Useful for scheduled cleanup jobs)
        """
        self.auto_delete = True
        self.save(update_fields=["auto_delete"])
        logger.info(f"⚙️ Notification flagged for auto-delete: {self}")

    def __str__(self):
        """Readable name for admin and shell."""
        status = "✅ Read" if self.is_read else "🕐 Unread"
        return f"[{status}] {self.employee} — {self.message[:60]}"
