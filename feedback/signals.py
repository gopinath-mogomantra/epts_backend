# ===========================================================
# feedback/signals.py (Enhanced)
# ===========================================================
"""
Enhanced signal handlers for feedback with notification integration.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

from .models import GeneralFeedback, ManagerFeedback, ClientFeedback

logger = logging.getLogger(__name__)


@receiver(post_save, sender=GeneralFeedback)
@receiver(post_save, sender=ManagerFeedback)
@receiver(post_save, sender=ClientFeedback)
def feedback_saved_handler(sender, instance, created, **kwargs):
    """
    Handle feedback save events.
    - Clear cache
    - Log activity
    - Send notifications (handled in model)
    """
    if not created:
        # Feedback was updated
        logger.info(f"[{sender.__name__}] Updated: {instance.id}")
        
        # Clear cache for employee
        if instance.employee and instance.employee.user:
            cache_key = f"feedback_summary_{instance.employee.user.id}"
            cache.delete(cache_key)


@receiver(post_delete, sender=GeneralFeedback)
@receiver(post_delete, sender=ManagerFeedback)
@receiver(post_delete, sender=ClientFeedback)
def feedback_deleted_handler(sender, instance, **kwargs):
    """
    Handle feedback deletion.
    - Clear cache
    - Log deletion
    """
    logger.info(f"[{sender.__name__}] Deleted: {instance.id}")
    
    # Clear cache for employee
    if instance.employee and instance.employee.user:
        cache_key = f"feedback_summary_{instance.employee.user.id}"
        cache.delete(cache_key)