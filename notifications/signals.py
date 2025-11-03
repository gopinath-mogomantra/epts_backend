# ===============================================
# notifications/signals.py
# ===============================================
"""
Signal handlers for the notifications app.

Handles:
- Performance notifications
- Attendance notifications
- Leave request notifications
- Feedback notifications
- Cache invalidation
- Push notification integration (optional)
"""

from django.dispatch import receiver, Signal
from django.db.models.signals import post_save, post_delete
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

from .models import Notification

logger = logging.getLogger(__name__)


# ===========================================================
# Custom Signals
# ===========================================================

# Performance-related signals
performance_posted = Signal()  # Args: employee, evaluation_period, score, source_user
performance_updated = Signal()  # Args: employee, evaluation_period, source_user

# Attendance-related signals
attendance_flagged = Signal()  # Args: employee, date, issue_type, severity

# Leave-related signals
leave_approved = Signal()  # Args: employee, leave_request, approved_by
leave_rejected = Signal()  # Args: employee, leave_request, rejected_by, reason

# Feedback-related signals
feedback_received = Signal()  # Args: employee, feedback, from_user


# ===========================================================
# Cache Invalidation Signals
# ===========================================================

@receiver(post_save, sender=Notification)
def invalidate_notification_cache_on_save(sender, instance, created, **kwargs):
    """
    Invalidate cached notification count and metadata when notification is saved.
    
    Args:
        sender: Notification model
        instance: Notification instance
        created: True if new notification was created
    """
    employee_id = instance.employee.id
    
    # Clear unread count cache
    cache.delete(f"unread_count_{employee_id}")
    
    # Clear metadata cache
    cache.delete(f"notification_metadata_{employee_id}")
    
    if created:
        logger.debug(f"Cache invalidated for user {employee_id} (new notification)")


@receiver(post_delete, sender=Notification)
def invalidate_notification_cache_on_delete(sender, instance, **kwargs):
    """
    Invalidate cached notification count and metadata when notification is deleted.
    
    Args:
        sender: Notification model
        instance: Notification instance
    """
    employee_id = instance.employee.id
    
    # Clear caches
    cache.delete(f"unread_count_{employee_id}")
    cache.delete(f"notification_metadata_{employee_id}")
    
    logger.debug(f"Cache invalidated for user {employee_id} (notification deleted)")


# ===========================================================
# Performance Notification Handlers
# ===========================================================

@receiver(performance_posted)
def on_performance_posted(sender, employee, evaluation_period, score=None, source_user=None, **kwargs):
    """
    Create notification when performance evaluation is posted.
    
    Args:
        sender: Signal sender
        employee: Employee receiving the evaluation
        evaluation_period: Evaluation period (e.g., "Week 44, 2025")
        score: Optional performance score
        source_user: User who posted the evaluation
    """
    if not employee:
        logger.warning("performance_posted signal received with no employee")
        return
    
    # Don't notify admins about their own performance posts
    if hasattr(employee, 'role') and employee.role == 'Admin':
        return
    
    # Build message
    if score is not None:
        message = f"Your performance evaluation for {evaluation_period} is published (Score: {score})."
    else:
        message = f"Your performance evaluation for {evaluation_period} is published."
    
    # Determine priority based on score (if available)
    priority = Notification.PRIORITY_MEDIUM
    if score is not None:
        if score >= 90:
            priority = Notification.PRIORITY_HIGH  # Excellent performance
        elif score < 60:
            priority = Notification.PRIORITY_HIGH  # Needs attention
    
    try:
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=Notification.CATEGORY_PERFORMANCE,
            priority=priority,
            link=f"/performance/?period={evaluation_period}",
            auto_delete=False,  # Keep performance notifications
            metadata={
                'evaluation_period': evaluation_period,
                'score': score,
                'posted_by': source_user.username if source_user else 'System',
            }
        )
        
        logger.info(
            f"Performance notification created for {employee.username} "
            f"(period: {evaluation_period}, score: {score})"
        )
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create performance notification: {e}")
        return None


@receiver(performance_updated)
def on_performance_updated(sender, employee, evaluation_period, source_user=None, **kwargs):
    """
    Create notification when performance evaluation is updated.
    
    Args:
        sender: Signal sender
        employee: Employee whose evaluation was updated
        evaluation_period: Evaluation period
        source_user: User who updated the evaluation
    """
    if not employee:
        return
    
    message = f"Your performance evaluation for {evaluation_period} has been updated."
    
    try:
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=Notification.CATEGORY_PERFORMANCE,
            priority=Notification.PRIORITY_MEDIUM,
            link=f"/performance/?period={evaluation_period}",
            auto_delete=False,
            metadata={
                'evaluation_period': evaluation_period,
                'updated_by': source_user.username if source_user else 'System',
                'updated_at': timezone.now().isoformat(),
            }
        )
        
        logger.info(f"Performance update notification created for {employee.username}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create performance update notification: {e}")
        return None


# ===========================================================
# Attendance Notification Handlers
# ===========================================================

@receiver(attendance_flagged)
def on_attendance_flagged(sender, employee, date, issue_type, severity='medium', **kwargs):
    """
    Create notification when attendance issue is flagged.
    
    Args:
        sender: Signal sender
        employee: Employee with attendance issue
        date: Date of the issue
        issue_type: Type of issue (late, absent, etc.)
        severity: Severity level (low, medium, high, urgent)
    """
    if not employee:
        return
    
    # Map severity to priority
    priority_map = {
        'low': Notification.PRIORITY_LOW,
        'medium': Notification.PRIORITY_MEDIUM,
        'high': Notification.PRIORITY_HIGH,
        'urgent': Notification.PRIORITY_URGENT,
    }
    priority = priority_map.get(severity, Notification.PRIORITY_MEDIUM)
    
    # Build message based on issue type
    issue_messages = {
        'late': f"You were marked late on {date}. Please review your attendance record.",
        'absent': f"You were marked absent on {date}. Please contact HR if this is incorrect.",
        'early_departure': f"Early departure recorded on {date}. Please ensure proper approval.",
        'missing_checkin': f"Missing check-in detected for {date}. Please update your attendance.",
        'missing_checkout': f"Missing check-out detected for {date}. Please update your attendance.",
    }
    
    message = issue_messages.get(issue_type, f"Attendance issue flagged for {date}. Please review.")
    
    try:
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=Notification.CATEGORY_ATTENDANCE,
            priority=priority,
            link=f"/attendance/?date={date}",
            auto_delete=False,  # Keep attendance issues
            expires_at=timezone.now() + timedelta(days=30),  # Expire after 30 days
            metadata={
                'date': str(date),
                'issue_type': issue_type,
                'severity': severity,
            }
        )
        
        logger.info(
            f"Attendance notification created for {employee.username} "
            f"(issue: {issue_type}, date: {date})"
        )
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create attendance notification: {e}")
        return None


# ===========================================================
# Leave Request Notification Handlers
# ===========================================================

@receiver(leave_approved)
def on_leave_approved(sender, employee, leave_request, approved_by, **kwargs):
    """
    Create notification when leave request is approved.
    
    Args:
        sender: Signal sender
        employee: Employee whose leave was approved
        leave_request: Leave request instance
        approved_by: User who approved the leave
    """
    if not employee:
        return
    
    start_date = getattr(leave_request, 'start_date', 'N/A')
    end_date = getattr(leave_request, 'end_date', 'N/A')
    leave_type = getattr(leave_request, 'leave_type', 'leave')
    
    message = (
        f"Your {leave_type} request from {start_date} to {end_date} "
        f"has been approved by {approved_by.get_full_name() or approved_by.username}."
    )
    
    try:
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=Notification.CATEGORY_LEAVE,
            priority=Notification.PRIORITY_HIGH,
            link=f"/leave/requests/{leave_request.id}/",
            auto_delete=False,
            metadata={
                'leave_request_id': leave_request.id,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'leave_type': leave_type,
                'approved_by': approved_by.username,
                'status': 'approved',
            }
        )
        
        logger.info(f"Leave approval notification created for {employee.username}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create leave approval notification: {e}")
        return None


@receiver(leave_rejected)
def on_leave_rejected(sender, employee, leave_request, rejected_by, reason=None, **kwargs):
    """
    Create notification when leave request is rejected.
    
    Args:
        sender: Signal sender
        employee: Employee whose leave was rejected
        leave_request: Leave request instance
        rejected_by: User who rejected the leave
        reason: Optional rejection reason
    """
    if not employee:
        return
    
    start_date = getattr(leave_request, 'start_date', 'N/A')
    end_date = getattr(leave_request, 'end_date', 'N/A')
    leave_type = getattr(leave_request, 'leave_type', 'leave')
    
    message = (
        f"Your {leave_type} request from {start_date} to {end_date} "
        f"has been rejected by {rejected_by.get_full_name() or rejected_by.username}."
    )
    
    if reason:
        message += f" Reason: {reason}"
    
    try:
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=Notification.CATEGORY_LEAVE,
            priority=Notification.PRIORITY_URGENT,  # Rejections are urgent
            link=f"/leave/requests/{leave_request.id}/",
            auto_delete=False,
            metadata={
                'leave_request_id': leave_request.id,
                'start_date': str(start_date),
                'end_date': str(end_date),
                'leave_type': leave_type,
                'rejected_by': rejected_by.username,
                'rejection_reason': reason,
                'status': 'rejected',
            }
        )
        
        logger.info(f"Leave rejection notification created for {employee.username}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create leave rejection notification: {e}")
        return None


# ===========================================================
# Feedback Notification Handlers
# ===========================================================

@receiver(feedback_received)
def on_feedback_received(sender, employee, feedback, from_user, **kwargs):
    """
    Create notification when employee receives feedback.
    
    Args:
        sender: Signal sender
        employee: Employee receiving feedback
        feedback: Feedback instance or content
        from_user: User who provided feedback
    """
    if not employee:
        return
    
    from_name = from_user.get_full_name() or from_user.username if from_user else "Anonymous"
    
    message = f"You have received new feedback from {from_name}."
    
    # Determine priority based on feedback type if available
    priority = Notification.PRIORITY_MEDIUM
    if hasattr(feedback, 'feedback_type'):
        if feedback.feedback_type in ['critical', 'improvement']:
            priority = Notification.PRIORITY_HIGH
    
    try:
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=Notification.CATEGORY_FEEDBACK,
            priority=priority,
            link=f"/feedback/{feedback.id}/" if hasattr(feedback, 'id') else "/feedback/",
            auto_delete=False,
            metadata={
                'feedback_id': feedback.id if hasattr(feedback, 'id') else None,
                'from_user': from_user.username if from_user else 'Anonymous',
                'feedback_type': getattr(feedback, 'feedback_type', 'general'),
            }
        )
        
        logger.info(f"Feedback notification created for {employee.username}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create feedback notification: {e}")
        return None


# ===========================================================
# Push Notification Integration (Optional)
# ===========================================================

@receiver(post_save, sender=Notification)
def send_push_notification(sender, instance, created, **kwargs):
    """
    Send push notification for urgent notifications.
    Integrate with your push notification service (Firebase, OneSignal, etc.)
    
    Args:
        sender: Notification model
        instance: Notification instance
        created: True if new notification
    """
    if not created:
        return
    
    # Only send push for urgent and high priority notifications
    if instance.priority not in [Notification.PRIORITY_URGENT, Notification.PRIORITY_HIGH]:
        return
    
    # TODO: Integrate with your push notification service
    # Example:
    # if hasattr(instance.employee, 'push_token') and instance.employee.push_token:
    #     try:
    #         send_push_to_device(
    #             token=instance.employee.push_token,
    #             title=f"{instance.get_category_display()} Notification",
    #             body=instance.message,
    #             data={'notification_id': instance.id, 'link': instance.link}
    #         )
    #         logger.info(f"Push notification sent to {instance.employee.username}")
    #     except Exception as e:
    #         logger.error(f"Failed to send push notification: {e}")
    
    logger.debug(
        f"Push notification hook called for {instance.employee.username} "
        f"(priority: {instance.priority})"
    )


# ===========================================================
# Helper Functions
# ===========================================================

def create_system_notification(
    employee,
    message,
    priority=Notification.PRIORITY_MEDIUM,
    link=None,
    auto_delete=True,
    expires_in_days=None,
    metadata=None
):
    """
    Helper function to create system notifications.
    
    Args:
        employee: Employee to notify
        message: Notification message
        priority: Priority level
        link: Optional link
        auto_delete: Auto-delete after reading
        expires_in_days: Days until expiration
        metadata: Additional metadata
    
    Returns:
        Notification instance or None
    """
    try:
        expires_at = None
        if expires_in_days:
            expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=Notification.CATEGORY_SYSTEM,
            priority=priority,
            link=link,
            auto_delete=auto_delete,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        logger.info(f"System notification created for {employee.username}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create system notification: {e}")
        return None


def create_announcement(
    department,
    message,
    priority=Notification.PRIORITY_MEDIUM,
    link=None,
    expires_in_days=7,
):
    """
    Helper function to create department-wide announcements.
    
    Args:
        department: Department instance
        message: Announcement message
        priority: Priority level
        link: Optional link
        expires_in_days: Days until expiration (default: 7)
    
    Returns:
        List of created Notification instances
    """
    try:
        expires_at = timezone.now() + timedelta(days=expires_in_days)
        
        notifications = Notification.objects.create_for_department(
            department=department,
            message=message,
            category=Notification.CATEGORY_ANNOUNCEMENT,
            priority=priority,
            link=link,
            auto_delete=True,
            expires_at=expires_at,
        )
        
        logger.info(
            f"Created {len(notifications)} announcement notifications "
            f"for department {department.name}"
        )
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to create announcement notifications: {e}")
        return []


# ===========================================================
# Usage Examples
# ===========================================================
"""
# In your performance app (performance/views.py or performance/signals.py):

from notifications.signals import performance_posted

# After creating/updating performance record:
performance_posted.send(
    sender=self.__class__,
    employee=performance.employee,
    evaluation_period="Week 44, 2025",
    score=performance.score,
    source_user=request.user
)


# In your attendance app:

from notifications.signals import attendance_flagged

attendance_flagged.send(
    sender=self.__class__,
    employee=employee,
    date="2025-11-01",
    issue_type='late',
    severity='medium'
)


# In your leave app:

from notifications.signals import leave_approved, leave_rejected

# On approval:
leave_approved.send(
    sender=self.__class__,
    employee=leave_request.employee,
    leave_request=leave_request,
    approved_by=request.user
)

# On rejection:
leave_rejected.send(
    sender=self.__class__,
    employee=leave_request.employee,
    leave_request=leave_request,
    rejected_by=request.user,
    reason="Insufficient leave balance"
)


# System notifications:

from notifications.signals import create_system_notification

create_system_notification(
    employee=user,
    message="System maintenance scheduled for tomorrow",
    priority=Notification.PRIORITY_HIGH,
    expires_in_days=1
)


# Department announcements:

from notifications.signals import create_announcement

create_announcement(
    department=it_dept,
    message="Team building event next Friday",
    priority=Notification.PRIORITY_MEDIUM,
    expires_in_days=7
)
"""