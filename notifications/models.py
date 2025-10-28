# ===========================================================
# notifications/models.py  ✅ Final Production-Ready Version
# ===========================================================
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
    - Persistent read records
    - Optional department broadcast notifications
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

    category = models.CharField(
        max_length=50,
        default="performance",
        help_text="Category of the notification (performance, feedback, system, etc.)",
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

    auto_delete = models.BooleanField(
        default=True,
        help_text="If True → delete automatically after being read. "
                  "If False → keep record marked as read.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the notification was created.",
    )

    # =======================================================
    # 🔹 Optional Departmental Broadcast (Future Scope)
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
    # 🔹 Meta & Indexing
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
    # 🔹 Utility Methods
    # =======================================================
    def mark_as_read(self, auto_commit=True):
        """
        Marks this notification as read and handles auto-deletion.
        """
        if self.is_read:
            logger.debug(f"🔁 Notification already read: {self}")
            return

        self.is_read = True
        self.read_at = timezone.now()

        if auto_commit:
            self.save(update_fields=["is_read", "read_at"])
            logger.info(f"📬 Notification marked as read for {self.employee} at {self.read_at}")

        if self.auto_delete:
            logger.info(f"🗑️ Auto-deleting read notification for {self.employee}: {self.message[:50]}")
            self.delete()

    def mark_as_unread(self, auto_commit=True):
        """Reverts a notification back to unread (admin/testing use)."""
        if not self.is_read:
            return
        self.is_read = False
        self.read_at = None
        if auto_commit:
            self.save(update_fields=["is_read", "read_at"])
            logger.info(f"🔄 Notification reverted to unread for {self.employee}")

    def soft_delete(self):
        """Marks notification for auto-cleanup (without deleting immediately)."""
        self.auto_delete = True
        self.save(update_fields=["auto_delete"])
        logger.info(f"⚙️ Notification flagged for auto-delete: {self}")

    def __str__(self):
        """Readable display name for admin and shell."""
        status = "✅ Read" if self.is_read else "🕐 Unread"
        return f"[{status}] {self.employee} — {self.message[:60]}"
