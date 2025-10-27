from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver

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
        help_text="Optional short code (e.g., HR01, IT02).",
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
        return self.name

    @property
    def display_name(self):
        """Used in dropdowns and frontend tables."""
        return f"{self.name} ({self.code})" if self.code else self.name

    def deactivate(self):
        """Soft deactivate a department (used by Admin panel)."""
        self.is_active = False
        self.save(update_fields=["is_active", "updated_at"])

    def activate(self):
        """Re-activate a previously inactive department."""
        self.is_active = True
        self.save(update_fields=["is_active", "updated_at"])


# ===========================================================
# ✅ EMPLOYEE MODEL
# ===========================================================
class Employee(models.Model):
    """
    Represents an employee linked to a user account.
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
        help_text="Job title or position (e.g., Developer, Analyst).",
    )

    contact_number = models.CharField(
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
        help_text="Employee contact number.",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Active",
        help_text="Current employment status.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Marks whether employee is currently active in the system.",
    )

    joining_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -------------------------------------------------------
    # Meta Info
    # -------------------------------------------------------
    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ["user__first_name"]
        indexes = [
            models.Index(fields=["department"]),
            models.Index(fields=["manager"]),
            models.Index(fields=["status"]),
        ]

    # -------------------------------------------------------
    # String Representation
    # -------------------------------------------------------
    def __str__(self):
        """Readable employee name with emp_id for admin tables."""
        if hasattr(self, "user") and self.user:
            full_name = f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username
            emp_id = getattr(self.user, "emp_id", "N/A")
            return f"{full_name} ({emp_id})"
        return "Unassigned Employee"

    # -------------------------------------------------------
    # Validation
    # -------------------------------------------------------
    def clean(self):
        """
        Prevent invalid manager assignments:
        - Employee cannot be their own manager.
        - Manager must have role='Manager' or 'Admin'.
        """
        if self.manager and self.manager_id == self.id:
            raise ValidationError("An employee cannot be their own manager.")
        if self.manager and getattr(self.manager.user, "role", None) not in ["Manager", "Admin"]:
            raise ValidationError("Assigned manager must have a Manager or Admin role.")

    # -------------------------------------------------------
    # Computed Fields (Frontend Usage)
    # -------------------------------------------------------
    @property
    def emp_id(self):
        """Shortcut to get emp_id from linked User."""
        return getattr(self.user, "emp_id", None)

    @property
    def email(self):
        """Shortcut to get email from linked User."""
        return getattr(self.user, "email", None)

    @property
    def user_role(self):
        """Shortcut to get role from linked User."""
        return getattr(self.user, "role", None)

    @property
    def department_name(self):
        """Return department name for frontend display."""
        return getattr(self.department, "name", "-")

    @property
    def manager_name(self):
        """Return manager's full name for frontend tables."""
        if self.manager and hasattr(self.manager, "user"):
            mgr_user = self.manager.user
            full_name = f"{mgr_user.first_name} {mgr_user.last_name}".strip()
            return full_name or mgr_user.username
        return "-"

    @property
    def reporting_to_name(self):
        """Alias for manager_name for frontend display consistency."""
        return self.manager_name

    @property
    def team_size(self):
        """Return number of direct team members reporting to this employee."""
        return self.team_members.filter(is_active=True).count()

    # -------------------------------------------------------
    # Activation / Deactivation Utilities
    # -------------------------------------------------------
    def deactivate(self):
        """Soft deactivate employee (status = Inactive, is_active=False)."""
        self.status = "Inactive"
        self.is_active = False
        self.save(update_fields=["status", "is_active", "updated_at"])

    def activate(self):
        """Re-activate a previously inactive employee."""
        self.status = "Active"
        self.is_active = True
        self.save(update_fields=["status", "is_active", "updated_at"])

    # -------------------------------------------------------
    # Query Helpers (For Manager & HR Views)
    # -------------------------------------------------------
    @classmethod
    def active_employees(cls):
        """Return queryset of all active employees."""
        return cls.objects.filter(is_active=True, status="Active")

    @classmethod
    def get_by_department(cls, dept_name):
        """Filter employees by department name."""
        return cls.objects.filter(department__name__iexact=dept_name, is_active=True)

    @classmethod
    def get_team_members(cls, manager):
        """Return all team members under a manager."""
        return cls.objects.filter(manager=manager, is_active=True)


# ===========================================================
# ✅ SIGNALS — Auto Create Employee on User Creation
# ===========================================================
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def auto_create_employee_profile(sender, instance, created, **kwargs):
    """
    Automatically create an Employee profile when a new User is created,
    if the role is not Admin (Admin users are excluded).
    """
    if created and getattr(instance, "role", None) in ["Manager", "Employee"]:
        from employee.models import Employee  # Local import to avoid circular dependency
        if not hasattr(instance, "employee_profile"):
            Employee.objects.create(
                user=instance,
                department=instance.department if hasattr(instance, "department") else None,
                role=instance.role,
                status="Active",
                joining_date=getattr(instance, "joining_date", timezone.now().date()),
            )
