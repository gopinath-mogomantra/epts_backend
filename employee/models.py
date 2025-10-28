# ===========================================================
# employee/models.py (Final — Frontend & Business Logic Aligned)
# ===========================================================

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger("employee")

User = settings.AUTH_USER_MODEL


# ===========================================================
# ✅ DEPARTMENT MODEL
# ===========================================================
class Department(models.Model):
    """
    Stores all departments in the organization.
    Used for dropdowns, filters, and task/feedback assignment.
    """

    code = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True,
        help_text="Short department code (e.g., HR01, ENG02).",
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        """Used in dropdowns and frontend tables."""
        return f"{self.name} ({self.code})" if self.code else self.name

    def deactivate(self):
        """Soft deactivate a department."""
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])
        logger.info(f"Department '{self.name}' deactivated.")

    def activate(self):
        """Re-activate a department."""
        self.is_active = True
        self.save(update_fields=["is_active", "updated_at"])
        logger.info(f"Department '{self.name}' reactivated.")


# ===========================================================
# ✅ EMPLOYEE MODEL
# ===========================================================
class Employee(models.Model):
    """
    Represents an employee linked to a User account.
    Includes department, manager, role, and contact info.
    """

    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Employee", "Employee"),
    ]

    STATUS_CHOICES = [
        ("Active", "Active"),
        ("On Leave", "On Leave"),
        ("Resigned", "Resigned"),
        ("Inactive", "Inactive"),
    ]

    # -------------------------------------------------------
    # Core Relations
    # -------------------------------------------------------
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        help_text="Linked user account for authentication and login.",
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        help_text="Department where the employee works.",
    )

    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_members",
        help_text="Reporting manager for the employee.",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="Employee",
        help_text="Employee's role (Admin, Manager, Employee).",
    )

    designation = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Job title (e.g., Developer, Analyst).",
    )

    # Frontend field name consistency: 'phone'
    phone = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        validators=[
            RegexValidator(
                r"^\+91[6-9]\d{9}$",
                "Enter a valid Indian mobile number with +91 prefix.",
            )
        ],
        help_text="Employee phone number.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Active",
        help_text="Current employment status.",
    )

    is_active = models.BooleanField(default=True)

    joining_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ["user__first_name"]
        indexes = [
            models.Index(fields=["department"]),
            models.Index(fields=["manager"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        """Readable employee name with emp_id."""
        if hasattr(self, "user") and self.user:
            full_name = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
            emp_id = getattr(self.user, "emp_id", "N/A")
            return f"{full_name} ({emp_id})"
        return "Unassigned Employee"

    # -------------------------------------------------------
    # VALIDATION
    # -------------------------------------------------------
    def clean(self):
        """Validate manager and department consistency."""
        if self.manager and self.manager_id == self.id:
            raise ValidationError("An employee cannot be their own manager.")
        if self.manager and getattr(self.manager.user, "role", None) not in ["Manager", "Admin"]:
            raise ValidationError("Assigned manager must have a Manager or Admin role.")
        if self.role == "Employee" and not self.department:
            raise ValidationError("Employee must belong to a department.")

    # -------------------------------------------------------
    # PROPERTIES
    # -------------------------------------------------------
    @property
    def emp_id(self):
        return getattr(self.user, "emp_id", None)

    @property
    def email(self):
        return getattr(self.user, "email", None)

    @property
    def user_role(self):
        return getattr(self.user, "role", None)

    @property
    def department_name(self):
        return getattr(self.department, "name", "-")

    @property
    def manager_name(self):
        if self.manager and hasattr(self.manager, "user"):
            mgr_user = self.manager.user
            full_name = f"{mgr_user.first_name} {mgr_user.last_name}".strip()
            return full_name or mgr_user.username
        return "-"

    @property
    def reporting_to_name(self):
        return self.manager_name

    @property
    def team_size(self):
        return self.team_members.filter(is_active=True).count()

    # -------------------------------------------------------
    # ACTIVATION / DEACTIVATION
    # -------------------------------------------------------
    def deactivate(self):
        """Soft deactivate employee."""
        self.status = "Inactive"
        self.is_active = False
        self.save(update_fields=["status", "is_active", "updated_at"])
        logger.warning(f"Employee {self.emp_id} deactivated.")

    def activate(self):
        """Re-activate employee."""
        self.status = "Active"
        self.is_active = True
        self.save(update_fields=["status", "is_active", "updated_at"])
        logger.info(f"Employee {self.emp_id} reactivated.")

    # -------------------------------------------------------
    # QUERY HELPERS
    # -------------------------------------------------------
    @classmethod
    def active_employees(cls):
        return cls.objects.filter(is_active=True, status="Active")

    @classmethod
    def get_by_department(cls, dept_name):
        return cls.objects.filter(department__name__iexact=dept_name, is_active=True)

    @classmethod
    def get_team_members(cls, manager):
        return cls.objects.filter(manager=manager, is_active=True)


# ===========================================================
# ✅ SIGNAL — Auto Create Employee on User Creation
# ===========================================================
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def auto_create_employee_profile(sender, instance, created, **kwargs):
    """Auto-create Employee profile when User is created."""
    try:
        if created and getattr(instance, "role", None) in ["Manager", "Employee"]:
            from employee.models import Employee
            if not hasattr(instance, "employee_profile"):
                Employee.objects.create(
                    user=instance,
                    department=getattr(instance, "department", None),
                    role=instance.role,
                    status="Active",
                    joining_date=getattr(instance, "joining_date", timezone.now().date()),
                )
                logger.info(f"Employee profile auto-created for {instance.emp_id}.")
    except Exception as e:
        logger.warning(f"Auto-create employee failed for {instance.emp_id}: {e}")
