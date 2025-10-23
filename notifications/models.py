# ===============================================
# notifications/models.py
# ===============================================

from django.db import models
from django.conf import settings
from django.utils import timezone


class Notification(models.Model):
    """
    Notification model that supports two behaviors:
    1. Auto-delete after read (temporary)
    2. Keep & mark as read (persistent)
    """

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="The user who will receive this notification."
    )
    message = models.CharField(max_length=255, help_text="Notification message text.")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    auto_delete = models.BooleanField(
        default=True,
        help_text="If True → delete after read; False → keep record as read."
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["employee", "is_read"])]

    def mark_as_read(self):
        """Mark as read (and delete if auto_delete=True)."""
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])

        if self.auto_delete:
            self.delete()

    def __str__(self):
        status = "✅ Read" if self.is_read else "🕐 Unread"
        return f"[{status}] {self.employee} - {self.message[:50]}"
