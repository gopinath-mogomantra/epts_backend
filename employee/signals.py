# ===========================================================
# employee/signals.py 
# ===========================================================
# Handles:
#   • Auto-update department employee count on employee create, update, delete
#   • Maintains real-time department analytics consistency
#   • Uses safe transaction handling and logging
# ===========================================================

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.conf import settings
from .models import Employee, Department
import logging

logger = logging.getLogger(__name__)


# ===========================================================
# Helper Function — Update Department Employee Count
# ===========================================================
def update_department_count(department):
    """
    Recalculate and update total active employees in a department.
    Called automatically after create/update/delete operations.
    """
    if not department:
        return

    try:
        # Count only active employees
        count = Employee.objects.filter(department=department, status="Active").count()
        Department.objects.filter(id=department.id).update(employee_count=count)
        logger.info(f"🏢 [DeptSync] {department.name} → Active Employees = {count}")
    except Exception as e:
        logger.warning(f"⚠️ [DeptSync] Failed to update count for {department}: {e}")


# ===========================================================
# PRE-SAVE — Track Department Change
# ===========================================================
@receiver(pre_save, sender=Employee)
def track_department_change(sender, instance, **kwargs):
    """
    Before saving, detect if employee is moving between departments.
    Store old department for later count adjustment.
    """
    if not instance.pk:
        # New employee — no old department to track
        instance._old_department_id = None
        return

    try:
        old_instance = Employee.objects.get(pk=instance.pk)
        instance._old_department_id = old_instance.department_id
    except Employee.DoesNotExist:
        instance._old_department_id = None


# ===========================================================
# POST-SAVE — Handle Create / Department Move
# ===========================================================
@receiver(post_save, sender=Employee)
def handle_employee_save(sender, instance, created, **kwargs):
    """
    After an employee is saved:
    - Increment department count if created
    - Adjust both old/new department counts if moved
    """
    def _update_counts():
        try:
            # Case 1: New Employee created
            if created:
                update_department_count(instance.department)
                return

            # Case 2: Department changed (old vs new)
            old_dept_id = getattr(instance, "_old_department_id", None)
            new_dept_id = instance.department_id

            if old_dept_id != new_dept_id:
                if old_dept_id:
                    old_dept = Department.objects.filter(id=old_dept_id).first()
                    update_department_count(old_dept)
                if new_dept_id:
                    update_department_count(instance.department)

        except Exception as e:
            logger.error(f"❌ [EmployeeSignal] Error updating department counts: {e}")

    transaction.on_commit(_update_counts)


# ===========================================================
# POST-DELETE — Handle Employee Removal
# ===========================================================
@receiver(post_delete, sender=Employee)
def handle_employee_delete(sender, instance, **kwargs):
    """
    After an employee is deleted, reduce the count of their department.
    """
    def _update_counts():
        update_department_count(instance.department)

    transaction.on_commit(_update_counts)
    logger.info(f"🗑️ [EmployeeSignal] Employee {instance.emp_id} deleted → Dept count updated.")


# ===========================================================
# INFO LOG
# ===========================================================
logger.info("✅ [EmployeeSignal] employee/signals.py successfully loaded.")
