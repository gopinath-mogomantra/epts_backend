# ===========================================================
# users/signals.py (Final — Auto Employee Creation)
# ===========================================================
# Automatically creates an Employee record whenever a new User
# is created (excluding staff and superusers).
# ===========================================================

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.db import transaction, IntegrityError
import logging

from employee.models import Employee, Department

User = settings.AUTH_USER_MODEL
logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_employee_for_user(sender, instance, created, **kwargs):
    """
    ✅ Auto-create Employee record for every new User.

    Business Logic:
    ----------------------------------------------------------
    • Triggered only on user creation (not update)
    • Skips superusers and staff accounts
    • Prevents duplicates if Employee already exists
    • Auto-generates unique emp_id if not provided
    • Optionally links department if defined
    """

    # 🛑 Skip if not a new user
    if not created:
        return

    # 🛑 Skip staff and superusers
    if getattr(instance, "is_superuser", False) or getattr(instance, "is_staff", False):
        logger.info(f"[User Signal] Skipped employee creation for admin/staff user: {instance.username}")
        return

    # 🛑 Skip if already linked
    if Employee.objects.filter(user=instance).exists():
        logger.warning(f"[User Signal] Employee record already exists for user: {instance.username}")
        return

    try:
        # ⚙️ Run inside transaction to ensure rollback safety
        with transaction.atomic():
            dept = getattr(instance, "department", None)
            department_obj = dept if isinstance(dept, Department) else None

            # Auto-generate emp_id if missing
            emp_id = getattr(instance, "emp_id", None)
            if not emp_id:
                emp_id = f"EMP{instance.id:04d}"

            employee = Employee.objects.create(
                user=instance,
                emp_id=emp_id,
                department=department_obj,
                status=getattr(instance, "status", "Active"),
                joining_date=getattr(instance, "joining_date", None),
            )

        logger.info(f"✅ [User Signal] Employee auto-created for user '{instance.username}' ({employee.emp_id})")

    except IntegrityError as e:
        logger.error(f"⚠️ [User Signal] Integrity error creating employee for {instance.username}: {e}")
    except Exception as e:
        logger.exception(f"⚠️ [User Signal] Unexpected error for {instance.username}: {e}")
