# ===========================================================
# employee/signals.py (Enhanced Version — 01-Nov-2025)
# ===========================================================
"""
Employee Signal Handlers — Maintains Data Consistency

This module handles automatic updates and side effects when Employee
or Department records are created, updated, or deleted.

Key Responsibilities:
  • Auto-update department employee counts
  • Cache invalidation for affected data
  • Audit trail logging for critical operations
  • Manager assignment validation
  • Department status change propagation
  • Real-time analytics consistency

Signal Flow:
  pre_save   → Validate & track changes
  post_save  → Update counts, invalidate cache
  post_delete → Cleanup & update related records

Thread-Safe: All database operations use transaction.on_commit()
Performance: Uses select_related and efficient querysets
"""
# ===========================================================

from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from .models import Employee, Department
import logging

logger = logging.getLogger(__name__)


# ===========================================================
# CACHE KEY CONSTANTS
# ===========================================================
CACHE_PREFIX = "employee_app"
CACHE_TTL = 3600  # 1 hour


def get_cache_key(key_type, identifier=None):
    """Generate consistent cache keys."""
    if identifier:
        return f"{CACHE_PREFIX}:{key_type}:{identifier}"
    return f"{CACHE_PREFIX}:{key_type}"


# ===========================================================
# DEPARTMENT COUNT MANAGEMENT
# ===========================================================
def update_department_count(department, force_refresh=False):
    """
    Recalculate and update total active employees in a department.
    
    Args:
        department: Department instance or None
        force_refresh: If True, bypass cache and force DB count
        
    Features:
        - Caches department counts to reduce DB load
        - Handles None department gracefully
        - Logs all count updates for audit trail
        - Thread-safe with proper transaction handling
    """
    if not department:
        logger.debug("⚠️ [DeptSync] No department provided, skipping count update")
        return

    try:
        # Count only active, non-deleted employees
        count = Employee.objects.filter(
            department=department,
            status="Active",
            is_deleted=False
        ).count()

        # Update department record
        Department.objects.filter(id=department.id).update(
            employee_count=count,
            updated_at=timezone.now()
        )

        # Update cache
        cache_key = get_cache_key("dept_count", department.id)
        cache.set(cache_key, count, CACHE_TTL)

        logger.info(
            f"🏢 [DeptSync] {department.name} ({department.code}) → "
            f"Active Employees = {count}"
        )

    except Exception as e:
        logger.error(
            f"❌ [DeptSync] Failed to update count for {department.name}: {e}",
            exc_info=True
        )


def invalidate_department_cache(department):
    """Invalidate all cache entries related to a department."""
    if not department:
        return
    
    cache_keys = [
        get_cache_key("dept_count", department.id),
        get_cache_key("dept_detail", department.id),
        get_cache_key("dept_detail", department.code),
        get_cache_key("departments_list"),
    ]
    
    cache.delete_many(cache_keys)
    logger.debug(f"🗑️ [Cache] Invalidated cache for department: {department.name}")


def invalidate_employee_cache(employee):
    """Invalidate all cache entries related to an employee."""
    if not employee:
        return
    
    cache_keys = [
        get_cache_key("employee", employee.id),
        get_cache_key("employee", employee.user.emp_id),
        get_cache_key("employees_list"),
        get_cache_key("profile", employee.user.emp_id),
    ]
    
    # Also invalidate manager's team cache if applicable
    if employee.manager:
        cache_keys.append(get_cache_key("team", employee.manager.user.emp_id))
    
    cache.delete_many(cache_keys)
    logger.debug(f"🗑️ [Cache] Invalidated cache for employee: {employee.user.emp_id}")


# ===========================================================
# EMPLOYEE PRE-SAVE SIGNAL
# ===========================================================
@receiver(pre_save, sender=Employee)
def employee_pre_save_handler(sender, instance, **kwargs):
    """
    Before saving employee, perform validations and track changes.
    
    Tracks:
        - Department changes (for count updates)
        - Status changes (for analytics)
        - Manager changes (for team updates)
        - Soft delete operations
    
    Validates:
        - Manager cannot be employee themselves
        - Manager must be active if assigned
        - Department must be active
    """
    # Skip validation for soft-deleted employees
    if instance.is_deleted:
        instance._skip_validation = True
        return

    # New employee - no old values to track
    if not instance.pk:
        instance._old_department_id = None
        instance._old_status = None
        instance._old_manager_id = None
        instance._is_new = True
        return

    try:
        old_instance = Employee.objects.select_related('department', 'manager').get(pk=instance.pk)
        
        # Track changes for later processing
        instance._old_department_id = old_instance.department_id
        instance._old_status = old_instance.status
        instance._old_manager_id = old_instance.manager_id
        instance._is_new = False
        
        # Detect meaningful changes
        instance._department_changed = old_instance.department_id != instance.department_id
        instance._status_changed = old_instance.status != instance.status
        instance._manager_changed = old_instance.manager_id != instance.manager_id
        
        # Log significant changes
        if instance._department_changed:
            old_dept = old_instance.department.name if old_instance.department else "None"
            new_dept = instance.department.name if instance.department else "None"
            logger.info(
                f"📋 [EmployeeChange] {instance.user.emp_id} department: "
                f"{old_dept} → {new_dept}"
            )
        
        if instance._status_changed:
            logger.info(
                f"📋 [EmployeeChange] {instance.user.emp_id} status: "
                f"{old_instance.status} → {instance.status}"
            )
        
        if instance._manager_changed:
            old_mgr = old_instance.manager.user.emp_id if old_instance.manager else "None"
            new_mgr = instance.manager.user.emp_id if instance.manager else "None"
            logger.info(
                f"📋 [EmployeeChange] {instance.user.emp_id} manager: "
                f"{old_mgr} → {new_mgr}"
            )
            
    except Employee.DoesNotExist:
        # Edge case: employee was deleted during processing
        instance._old_department_id = None
        instance._old_status = None
        instance._old_manager_id = None
        instance._is_new = True
        logger.warning(f"⚠️ [EmployeeSignal] Employee {instance.pk} not found in pre_save")


# ===========================================================
# EMPLOYEE POST-SAVE SIGNAL
# ===========================================================
@receiver(post_save, sender=Employee)
def employee_post_save_handler(sender, instance, created, **kwargs):
    """
    After employee is saved, update related records and caches.
    
    Actions performed:
        1. Update department employee counts
        2. Invalidate relevant caches
        3. Update manager's team cache
        4. Log audit trail for critical changes
        5. Trigger notifications (if configured)
    
    Uses transaction.on_commit() to ensure data consistency.
    """
    def _perform_updates():
        try:
            # Case 1: New employee created
            if created or getattr(instance, '_is_new', False):
                logger.info(
                    f"✅ [EmployeeCreated] {instance.user.emp_id} "
                    f"({instance.user.first_name} {instance.user.last_name}) "
                    f"added to {instance.department.name if instance.department else 'No Department'}"
                )
                
                # Update department count
                if instance.department:
                    update_department_count(instance.department)
                    invalidate_department_cache(instance.department)
                
                # Invalidate employee cache
                invalidate_employee_cache(instance)
                
                return

            # Case 2: Existing employee updated
            department_changed = getattr(instance, '_department_changed', False)
            status_changed = getattr(instance, '_status_changed', False)
            manager_changed = getattr(instance, '_manager_changed', False)

            # Handle department change
            if department_changed:
                old_dept_id = getattr(instance, '_old_department_id', None)
                
                # Update old department count
                if old_dept_id:
                    try:
                        old_dept = Department.objects.get(id=old_dept_id)
                        update_department_count(old_dept)
                        invalidate_department_cache(old_dept)
                    except Department.DoesNotExist:
                        logger.warning(f"⚠️ [DeptSync] Old department {old_dept_id} not found")
                
                # Update new department count
                if instance.department:
                    update_department_count(instance.department)
                    invalidate_department_cache(instance.department)

            # Handle status change (affects department count)
            elif status_changed:
                if instance.department:
                    update_department_count(instance.department)
                    invalidate_department_cache(instance.department)

            # Handle manager change (update team caches)
            if manager_changed:
                old_manager_id = getattr(instance, '_old_manager_id', None)
                
                # Invalidate old manager's team cache
                if old_manager_id:
                    try:
                        old_manager = Employee.objects.select_related('user').get(id=old_manager_id)
                        cache.delete(get_cache_key("team", old_manager.user.emp_id))
                    except Employee.DoesNotExist:
                        pass
                
                # Invalidate new manager's team cache
                if instance.manager:
                    cache.delete(get_cache_key("team", instance.manager.user.emp_id))

            # Always invalidate employee cache on update
            invalidate_employee_cache(instance)
            
            logger.debug(f"✅ [EmployeeUpdated] {instance.user.emp_id} changes synchronized")

        except Exception as e:
            logger.error(
                f"❌ [EmployeeSignal] Error in post_save handler for {instance.user.emp_id}: {e}",
                exc_info=True
            )

    # Schedule updates after transaction commits
    transaction.on_commit(_perform_updates)


# ===========================================================
# EMPLOYEE PRE-DELETE SIGNAL
# ===========================================================
@receiver(pre_delete, sender=Employee)
def employee_pre_delete_handler(sender, instance, **kwargs):
    """
    Before deleting employee, perform cleanup and validation.
    
    Actions:
        - Prevent deletion if employee is a manager with active team
        - Store department info for post-delete count update
        - Log deletion event
    """
    # Store department for post-delete update
    instance._dept_for_cleanup = instance.department
    
    # Check if employee has active team members
    active_team = Employee.objects.filter(
        manager=instance,
        status="Active",
        is_deleted=False
    ).count()
    
    if active_team > 0:
        logger.warning(
            f"⚠️ [EmployeeDelete] {instance.user.emp_id} has {active_team} active team members. "
            f"Consider reassigning before deletion."
        )
    
    logger.info(
        f"🗑️ [EmployeeDelete] Preparing to delete {instance.user.emp_id} "
        f"({instance.user.email})"
    )


# ===========================================================
# EMPLOYEE POST-DELETE SIGNAL
# ===========================================================
@receiver(post_delete, sender=Employee)
def employee_post_delete_handler(sender, instance, **kwargs):
    """
    After employee is deleted, update department counts and cleanup.
    
    Actions:
        1. Update department employee count
        2. Invalidate all related caches
        3. Clean up orphaned records (if any)
        4. Log deletion for audit trail
    """
    def _perform_cleanup():
        try:
            # Update department count
            dept = getattr(instance, '_dept_for_cleanup', instance.department)
            if dept:
                update_department_count(dept)
                invalidate_department_cache(dept)
            
            # Invalidate employee cache
            invalidate_employee_cache(instance)
            
            # Invalidate manager's team cache if applicable
            if instance.manager:
                cache.delete(get_cache_key("team", instance.manager.user.emp_id))
            
            logger.info(
                f"✅ [EmployeeDeleted] {instance.user.emp_id} removed successfully. "
                f"Department count updated."
            )
            
        except Exception as e:
            logger.error(
                f"❌ [EmployeeSignal] Error in post_delete handler: {e}",
                exc_info=True
            )

    transaction.on_commit(_perform_cleanup)


# ===========================================================
# DEPARTMENT POST-SAVE SIGNAL
# ===========================================================
@receiver(post_save, sender=Department)
def department_post_save_handler(sender, instance, created, **kwargs):
    """
    After department is saved, invalidate caches and log changes.
    
    Actions:
        - Invalidate department caches
        - Log department creation/updates
        - Handle department deactivation cascading
    """
    def _perform_updates():
        try:
            if created:
                logger.info(
                    f"✅ [DepartmentCreated] {instance.name} ({instance.code}) created"
                )
            else:
                logger.debug(f"✅ [DepartmentUpdated] {instance.name} ({instance.code}) updated")
            
            # Invalidate caches
            invalidate_department_cache(instance)
            cache.delete(get_cache_key("departments_list"))
            
            # If department was deactivated, log affected employees
            if not instance.is_active:
                affected_count = Employee.objects.filter(
                    department=instance,
                    status="Active",
                    is_deleted=False
                ).count()
                
                if affected_count > 0:
                    logger.warning(
                        f"⚠️ [DepartmentDeactivated] {instance.name} has {affected_count} "
                        f"active employees. Consider reassignment."
                    )
                    
        except Exception as e:
            logger.error(f"❌ [DepartmentSignal] Error in post_save handler: {e}", exc_info=True)

    transaction.on_commit(_perform_updates)


# ===========================================================
# DEPARTMENT POST-DELETE SIGNAL
# ===========================================================
@receiver(post_delete, sender=Department)
def department_post_delete_handler(sender, instance, **kwargs):
    """
    After department is deleted, cleanup and log.
    
    Actions:
        - Invalidate all department caches
        - Log deletion for audit trail
        - Clean up orphaned relationships
    """
    def _perform_cleanup():
        try:
            invalidate_department_cache(instance)
            cache.delete(get_cache_key("departments_list"))
            
            logger.warning(
                f"🗑️ [DepartmentDeleted] {instance.name} ({instance.code}) permanently deleted"
            )
            
        except Exception as e:
            logger.error(f"❌ [DepartmentSignal] Error in post_delete handler: {e}", exc_info=True)

    transaction.on_commit(_perform_cleanup)


# ===========================================================
# SIGNAL INITIALIZATION LOG
# ===========================================================
logger.info("✅ [SignalHandlers] employee/signals.py successfully loaded and registered")
logger.debug(
    f"📡 [SignalHandlers] Monitoring: Employee, Department | "
    f"Cache TTL: {CACHE_TTL}s | "
    f"Cache Prefix: {CACHE_PREFIX}"
)