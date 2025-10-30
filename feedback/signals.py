# ===========================================================
# feedback/signals.py ✅ Final — Multi-Feedback Model Safe Logic
# Employee Performance Tracking System (EPTS)
# ===========================================================

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps
from employee.models import Department
import logging

logger = logging.getLogger(__name__)

# ===========================================================
# Helper — Safe Model Loader
# ===========================================================
def get_feedback_models():
    """Safely load all feedback models without breaking startup."""
    try:
        GeneralFeedback = apps.get_model('feedback', 'GeneralFeedback')
        ManagerFeedback = apps.get_model('feedback', 'ManagerFeedback')
        ClientFeedback = apps.get_model('feedback', 'ClientFeedback')
        return [GeneralFeedback, ManagerFeedback, ClientFeedback]
    except LookupError:
        logger.warning("⚠️ Feedback models not ready — skipping signal registration.")
        return []


# ===========================================================
# Signal Receiver — Handles all Feedback Variants
# ===========================================================
@receiver(post_save)
def feedback_created_handler(sender, instance, created, **kwargs):
    """
    Post-save signal handler for all feedback model variants.
    Triggers notification/log when new feedback is created.
    """

    # Only handle events for defined feedback models
    feedback_models = get_feedback_models()
    if sender not in feedback_models:
        return

    if created:
        emp = getattr(instance, "employee", None)
        rating = getattr(instance, "rating", None)
        source = getattr(instance, "source_type", sender.__name__.replace("Feedback", ""))

        emp_name = None
        if emp and hasattr(emp, "user"):
            emp_name = f"{emp.user.first_name} {emp.user.last_name}".strip() or emp.user.username

        # Example logging (replace with actual notification/score logic)
        logger.info(
            f"✅ New {source} feedback created for employee: {emp_name or 'Unknown'} "
            f"(Rating: {rating}/10)"
        )

        # Optional: Trigger Notification Model if available
        try:
            Notification = apps.get_model("notifications", "Notification")
            if emp and hasattr(emp, "user"):
                Notification.objects.create(
                    employee=emp.user,
                    message=f"📢 New {source} feedback added — Rating: {rating}/10",
                    auto_delete=True,
                )
        except Exception as e:
            logger.warning(f"⚠️ Notification dispatch failed: {e}")
