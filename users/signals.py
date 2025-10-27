# ===========================================================
# users/signals.py — Auto-create Employee for new Users
# ===========================================================

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from employee.models import Employee, Department

User = settings.AUTH_USER_MODEL

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee_for_user(sender, instance, created, **kwargs):
    """
    Automatically create Employee record for each new User.
    Triggered for all creation methods (API, Admin panel, scripts, etc.)
    """
    if created:
        try:
            # Avoid duplication if already exists
            if not hasattr(instance, "employee"):
                dept = getattr(instance, "department", None)
                Employee.objects.create(
                    user=instance,
                    emp_id=instance.emp_id,
                    department=dept if isinstance(dept, Department) else None,
                    status=getattr(instance, "status", "Active"),
                    joining_date=getattr(instance, "joining_date", None)
                )
                print(f"✅ Employee auto-created for {instance.emp_id}")
        except Exception as e:
            print(f"⚠️ Signal Error (Employee auto-create failed): {e}")
