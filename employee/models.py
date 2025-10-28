# ===========================================================
# employee/models.py (Final — Business Logic & Frontend Aligned)
# ===========================================================
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# ===========================================================
# 🔹 Department Model
# ===========================================================
class Department(models.Model):
    """
    Represents organizational departments.
    Used in both Employee and Performance modules.
    """

    code = models.CharField(max_length=10, unique=True, help_text="Short department code (e.g., ENG01)")
    name = models.CharField(max_length=100, unique=True, help_text="Department name (e.g., Engineering)")
    description = models.TextField(blank=True, null=True, help_text="Optional department description.")

    employee_count = models.PositiveIntegerField(default=0, help_text="Total active employees in this department.")
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
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """Ensure valid code format."""
        if not self.code.isalnum():
            raise ValidationError({"code": "Department code must be alphanumeric."})


# ===========================================================
# 🔹 Employee Model
# ===========================================================
class Employee(models.Model):
    """
    Represents employee records within the organization.
    Linked to Django's User model (One-to-One).
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

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        help_text="Linked Django User account."
    )

    emp_id = models.CharField(
        max_length=20,
        unique=True,
        help_text="Unique Employee ID (e.g., EMP1001)."
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

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="Employee",
        help_text="Role in the organization."
    )

    joining_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")

    contact_number = models.CharField(max_length=15, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["emp_id"]
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        indexes = [
            models.Index(fields=["emp_id"]),
            models.Index(fields=["department"]),
            models.Index(fields=["status"]),
        ]

    # -----------------------------------------------------------
    # ✅ Validation
    # -----------------------------------------------------------
    def clean(self):
        """Custom validation for Employee creation."""
        if not self.emp_id:
            raise ValidationError({"emp_id": "Employee ID cannot be empty."})

        if not self.user.email:
            raise ValidationError({"user": "User email cannot be empty."})

        if Employee.objects.exclude(id=self.id).filter(user__email=self.user.email).exists():
            raise ValidationError({"user": "An employee with this email already exists."})

        if self.manager and self.manager == self:
            raise ValidationError({"manager": "An employee cannot be their own manager."})

    # -----------------------------------------------------------
    # ✅ Save Override
    # -----------------------------------------------------------
    def save(self, *args, **kwargs):
        """Ensure consistency in department and role assignments."""
        self.full_clean()

        # Enforce that only Managers can have team members
        if self.manager and self.manager.role != "Manager":
            raise ValidationError({"manager": "Assigned manager must have role 'Manager'."})

        super().save(*args, **kwargs)

    # -----------------------------------------------------------
    # ✅ Utility / Display Methods
    # -----------------------------------------------------------
    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return f"{self.emp_id} - {full_name or self.user.username}"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip()

    def get_department_name(self):
        return self.department.name if self.department else "-"

    def get_role_display_name(self):
        """Returns a readable role name."""
        return dict(self.ROLE_CHOICES).get(self.role, "Employee")
