from django.dispatch import receiver, Signal
from .models import Notification

# Custom signal that performance app can send: performance_posted
performance_posted = Signal(providing_args=["employee", "evaluation_period", "source_user"])

def create_performance_notification(employee, evaluation_period):
    """
    Helper: create a notification for the employee when performance is posted.
    """
    if not employee:
        return None

    message = f"Your weekly performance for {evaluation_period} is published."
    return Notification.objects.create(employee=employee, message=message, is_read=False)


# Example of a receiver if performance app sends a signal 'performance_posted'
# from performance.signals import performance_posted (defined in that app).
#
# @receiver(performance_posted)
# def on_performance_posted(sender, employee, evaluation_period, source_user=None, **kwargs):
#     # If you want to avoid notifying admins; ensure employee.role != 'Admin'
#     create_performance_notification(employee, evaluation_period)
