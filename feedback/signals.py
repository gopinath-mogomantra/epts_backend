# ===========================================================
# feedback/signals.py ✅ Safe Import (No Circular Import)
# Employee Performance Tracking System (EPTS)
# ===========================================================

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps

# ⚠️ Do NOT directly import Feedback — use lazy loading via apps.get_model

@receiver(post_save)
def feedback_created_handler(sender, instance, created, **kwargs):
    """
    Handles post-save signal for Feedback creation.
    Trigger notification or scoring logic when a new feedback is added.
    """
    Feedback = apps.get_model('feedback', 'Feedback')

    # Ensure this runs only for Feedback model
    if sender != Feedback:
        return

    if created:
        emp_id = getattr(instance, 'emp_id', None)
        rating = getattr(instance, 'rating', None)
        feedback_type = getattr(instance, 'feedback_type', None)

        # Example: Trigger a print/log (replace with Notification or Score update)
        print(f"✅ New {feedback_type} feedback created for Employee {emp_id} with rating {rating}/10")
