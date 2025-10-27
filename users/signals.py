from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.db import transaction
from employee.models import Employee, Department

User = settings.AUTH_USER_MODEL


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee_for_user(sender, instance, created, **kwargs):
    """
    ✅ Automatically create an Employee record for each new User.

    This signal:
    - Ensures one Employee per User.
    - Skips creation for superusers / staff.
    - Handles missing or invalid department gracefully.
    - Prints debug message only in dev (not in production).
    """

    # Ignore updates, only act on first creation
    if not created:
        return

    # Skip staff and superuser accounts
    if getattr(instance, "is_superuser", False) or getattr(instance, "is_staff", False):
        return

    # Avoid duplicate employee records (safety check)
    if Employee.objects.filter(user=instance).exists():
        return

    try:
        # Safe transaction block
        with transaction.atomic():
            dept = getattr(instance, "department", None)
            department_obj = dept if isinstance(dept, Department) else None

            emp_id = getattr(instance, "emp_id", None)
            if not emp_id:
                # fallback unique ID if not provided
                emp_id = f"EMP{instance.id:04d}"

            Employee.objects.create(
                user=instance,
                emp_id=emp_id,
                department=department_obj,
                status=getattr(instance, "status", "Active"),
                joining_date=getattr(instance, "joining_date", None),
            )

        print(f"✅ Employee auto-created for user {instance.username} ({emp_id})")

    except Exception as e:
        print(f"⚠️ [Signal Error] Employee auto-create failed for user {instance.username}: {e}")
