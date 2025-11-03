# ===========================================================
# employee/models.py (PRODUCTION-READY VERSION)
# ===========================================================
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
import os
import logging

logger = logging.getLogger("employee")
User = settings.AUTH_USER_MODEL


# ===========================================================
# Department Model
# ===========================================================
class Department(models.Model):
    """Represents organizational departments with employee count tracking."""

    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="Short department code (e.g., ENG01)"
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Department name (e.g., Engineering)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional department description."
    )
    employee_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """Validate department code format."""
        super().clean()
        
        if self.code and not self.code.isalnum():
            raise ValidationError({
                "code": "Department code must be alphanumeric."
            })
        
        # Normalize code to uppercase
        if self.code:
            self.code = self.code.upper()

    @transaction.atomic
    def update_employee_count(self):
        """
        Recalculate and update employee count atomically.
        Prevents race conditions with row-level locking.
        """
        # Lock the department row
        Department.objects.filter(pk=self.pk).select_for_update().first()
        
        # Count active, non-deleted employees
        count = self.employees.filter(
            status="Active",
            is_deleted=False
        ).count()
        
        # Update atomically using queryset update
        Department.objects.filter(pk=self.pk).update(
            employee_count=count,
            updated_at=timezone.now()
        )
        
        # Refresh instance to get updated values
        self.refresh_from_db(fields=['employee_count', 'updated_at'])
        
        logger.debug(
            f"Updated employee count for {self.code}: {count}",
            extra={'department': self.code, 'count': count}
        )


# ===========================================================
# Employee Model
# ===========================================================
class Employee(models.Model):
    """
    Represents employee records linked to the User model.
    Includes comprehensive validation and soft-delete support.
    """

    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("On Leave", "On Leave"),
    ]

    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Employee", "Employee"),
    ]

    # -----------------------------------------------------------
    # Core Relationships
    # -----------------------------------------------------------
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        help_text="Linked Django User account."
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        help_text="Department this employee belongs to."
    )
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_members",
        help_text="Reporting manager for this employee."
    )

    # -----------------------------------------------------------
    # Professional Fields
    # -----------------------------------------------------------
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="Employee"
    )
    designation = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    project_name = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Project the employee is working on"
    )
    joining_date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Active"
    )

    # -----------------------------------------------------------
    # Personal Information
    # -----------------------------------------------------------
    contact_number = models.CharField(
        max_length=15,
        blank=True,
        null=True
    )
    gender = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")]
    )
    dob = models.DateField(
        blank=True,
        null=True,
        help_text="Date of birth"
    )
    profile_picture = models.ImageField(
        upload_to="profile_pics/%Y/%m/%d",
        blank=True,
        null=True,
        help_text="Profile picture (JPG/PNG, max 5MB)"
    )

    # -----------------------------------------------------------
    # Address Information
    # -----------------------------------------------------------
    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=12, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)

    # -----------------------------------------------------------
    # System Flags
    # -----------------------------------------------------------
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag for employee."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -----------------------------------------------------------
    # Meta Configuration
    # -----------------------------------------------------------
    class Meta:
        ordering = ["user__emp_id"]
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["department"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_deleted"]),
            models.Index(fields=["manager"]),
        ]

    # -----------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------
    def __init__(self, *args, **kwargs):
        """Store original department ID for tracking changes."""
        super().__init__(*args, **kwargs)
        self._old_department_id = self.department_id if self.pk else None

    # -----------------------------------------------------------
    # String Representation
    # -----------------------------------------------------------
    def __str__(self):
        try:
            full_name = f"{self.user.first_name} {self.user.last_name}".strip()
            emp_id = getattr(self.user, "emp_id", "-")
            return f"{emp_id} - {full_name or self.user.username}"
        except Exception:
            return f"Employee #{self.pk}"

    # -----------------------------------------------------------
    # Utility Properties
    # -----------------------------------------------------------
    @property
    def emp_id(self):
        """Get employee ID from linked user."""
        return getattr(self.user, "emp_id", None)

    def get_full_name(self):
        """Get full name from linked user."""
        try:
            name = f"{self.user.first_name} {self.user.last_name}".strip()
            return name or self.user.username
        except Exception:
            return "Unknown"

    def get_department_name(self):
        """Get department name or fallback."""
        return self.department.name if self.department else "-"

    def get_manager_name(self):
        """Get manager's full name or fallback."""
        if self.manager and self.manager.user:
            return self.manager.get_full_name()
        return "-"

    def get_role_display_name(self):
        """Get human-readable role name."""
        return dict(self.ROLE_CHOICES).get(self.role, "Employee")

    # -----------------------------------------------------------
    # Validation Helpers
    # -----------------------------------------------------------
    def _check_circular_manager(self):
        """
        Check for circular manager relationships.
        Prevents infinite loops in organizational hierarchy.
        """
        if not self.manager or not self.pk:
            return
        
        visited = {self.pk}
        current = self.manager
        max_depth = 50  # Safety limit
        
        while current and len(visited) < max_depth:
            if current.pk in visited:
                raise ValidationError({
                    "manager": "Circular manager relationship detected."
                })
            visited.add(current.pk)
            current = current.manager
        
        if len(visited) >= max_depth:
            logger.error(
                f"Manager chain too deep for employee {self.emp_id}",
                extra={'emp_id': self.emp_id}
            )
            raise ValidationError({
                "manager": "Manager chain is too deep (possible data corruption)."
            })

    # -----------------------------------------------------------
    # Model Validation
    # -----------------------------------------------------------
    def clean(self):
        """
        Comprehensive model-level validation.
        Can be partially skipped by serializers via _skip_extended_validation flag.
        """
        super().clean()
        
        # Always check: deleted employee constraint
        if self.is_deleted and not hasattr(self, "_allow_deleted_save"):
            raise ValidationError({
                "employee": "This employee record has been deleted. No modifications allowed."
            })
        
        # Skip extended validation if explicitly requested (used by serializers)
        if hasattr(self, "_skip_extended_validation"):
            return
        
        # User validation
        if not self.user or not getattr(self.user, "email", None):
            raise ValidationError({
                "user": "Linked User must have a valid email."
            })
        
        # Email uniqueness check
        if self.user and self.user.email:
            duplicate = Employee.objects.exclude(pk=self.pk).filter(
                user__email__iexact=self.user.email
            ).exists()
            
            if duplicate:
                raise ValidationError({
                    "user": "An employee with this email already exists."
                })
        
        # Manager validation
        if self.manager:
            # Self-reference check
            if self.pk and self.manager.pk == self.pk:
                raise ValidationError({
                    "manager": "An employee cannot be their own manager."
                })
            
            # Circular reference check
            if self.pk:
                self._check_circular_manager()
            
            # Role validation
            manager_role = getattr(self.manager, "role", None)
            if manager_role not in ["Manager", "Admin"]:
                raise ValidationError({
                    "manager": "Assigned manager must have role 'Manager' or 'Admin'."
                })
        
        # Department validation
        if not self.department:
            raise ValidationError({
                "department": "Employee must belong to a department."
            })
        
        # Date validations
        if self.joining_date and self.joining_date > timezone.now().date():
            raise ValidationError({
                "joining_date": "Joining date cannot be in the future."
            })
        
        if self.dob:
            if self.dob > timezone.now().date():
                raise ValidationError({
                    "dob": "Date of birth cannot be in the future."
                })
            
            # Age validation (must be at least 18)
            age = (timezone.now().date() - self.dob).days // 365
            if age < 18:
                raise ValidationError({
                    "dob": "Employee must be at least 18 years old."
                })
        
        # Pincode validation
        if self.pincode and not self.pincode.isdigit():
            raise ValidationError({
                "pincode": "Pincode must contain only digits."
            })
        
        # Profile picture validation
        if self.profile_picture:
            # Check extension
            ext = os.path.splitext(self.profile_picture.name)[1].lower()
            if ext not in [".jpg", ".jpeg", ".png"]:
                raise ValidationError({
                    "profile_picture": "Only JPG and PNG images are allowed."
                })
            
            # Check file size (5MB limit)
            if self.profile_picture.size > 5 * 1024 * 1024:
                raise ValidationError({
                    "profile_picture": "Profile picture must be less than 5MB."
                })

    # -----------------------------------------------------------
    # Save Override
    # -----------------------------------------------------------
    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Save with proper validation and atomic department count updates.
        Handles department changes and maintains referential integrity.
        """
        # Allow saves for soft delete operation
        if self.is_deleted and not hasattr(self, "_allow_deleted_save"):
            raise ValidationError({
                "employee": "Cannot modify a deleted employee."
            })
        
        # Run validation unless explicitly skipped
        if not hasattr(self, "_skip_extended_validation"):
            self.full_clean()
        
        # Track if this is a new employee
        is_new = self.pk is None
        old_dept_id = None if is_new else self._old_department_id
        
        # Save the employee record
        super().save(*args, **kwargs)
        
        # Update old department ID tracker for next save
        self._old_department_id = self.department_id
        
        # Update department employee counts
        departments_to_update = set()
        
        if self.department_id:
            departments_to_update.add(self.department_id)
        
        if old_dept_id and old_dept_id != self.department_id:
            departments_to_update.add(old_dept_id)
        
        # Bulk update department counts
        for dept_id in departments_to_update:
            dept = Department.objects.filter(id=dept_id).first()
            if dept:
                dept.update_employee_count()

    # -----------------------------------------------------------
    # Soft Delete Logic
    # -----------------------------------------------------------
    @transaction.atomic
    def soft_delete(self):
        """
        Soft delete the employee and deactivate the user account.
        All operations are atomic to prevent inconsistent state.
        """
        if self.is_deleted:
            raise ValidationError({
                "employee": "This employee is already deleted."
            })
        
        # Lock both employee and user rows
        Employee.objects.filter(pk=self.pk).select_for_update().first()
        
        if self.user:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(pk=self.user.pk).select_for_update().first()
        
        # Mark as deleted
        self.is_deleted = True
        self.status = "Inactive"
        
        # Deactivate linked user account
        if self.user:
            self.user.is_active = False
            self.user.save(update_fields=["is_active"])
        
        # Set flag to allow save on deleted record
        self._allow_deleted_save = True
        
        try:
            # Save employee changes
            self.save(update_fields=["is_deleted", "status", "updated_at"])
            
            # Update department count
            if self.department:
                self.department.update_employee_count()
            
            logger.info(
                f"Employee soft deleted: {self.emp_id}",
                extra={'emp_id': self.emp_id}
            )
        finally:
            # Always clear the flag
            if hasattr(self, "_allow_deleted_save"):
                delattr(self, "_allow_deleted_save")
    
    @transaction.atomic
    def restore(self):
        """
        Restore a soft-deleted employee.
        Reactivates both employee and user records.
        """
        if not self.is_deleted:
            raise ValidationError({
                "employee": "This employee is not deleted."
            })
        
        # Lock rows
        Employee.objects.filter(pk=self.pk).select_for_update().first()
        
        if self.user:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            User.objects.filter(pk=self.user.pk).select_for_update().first()
        
        # Restore employee
        self.is_deleted = False
        self.status = "Active"
        
        # Reactivate user
        if self.user:
            self.user.is_active = True
            self.user.save(update_fields=["is_active"])
        
        # Allow save and update
        self._allow_deleted_save = True
        
        try:
            self.save(update_fields=["is_deleted", "status", "updated_at"])
            
            # Update department count
            if self.department:
                self.department.update_employee_count()
            
            logger.info(
                f"Employee restored: {self.emp_id}",
                extra={'emp_id': self.emp_id}
            )
        finally:
            if hasattr(self, "_allow_deleted_save"):
                delattr(self, "_allow_deleted_save")