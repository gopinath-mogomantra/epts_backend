# ===========================================================
# employee/models.py (Final — Business Logic & Frontend Aligned)
# ===========================================================
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# ===========================================================
# 🏢 Department Model
# ===========================================================
class Department(models.Model):
    """Represents organizational departments."""

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
    description = models.TextField(blank=True, null=True, help_text="Optional department description.")
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
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """Ensure department code format is valid."""
        if not self.code.isalnum():
            raise ValidationError({"code": "Department code must be alphanumeric."})

    # -------------------------------------------------------
    # Auto-update employee count for dashboards
    # -------------------------------------------------------
    def update_employee_count(self):
        """Recalculate and update employee count."""
        self.employee_count = self.employees.filter(status="Active").count()
        self.save(update_fields=["employee_count", "updated_at"])


# ===========================================================
# 👨‍💼 Employee Model
# ===========================================================
class Employee(models.Model):
    """Represents employee records linked to the User model."""

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
        ordering = ["user__emp_id"]
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["department"]),
            models.Index(fields=["role"]),
        ]

    # -----------------------------------------------------------
    # ✅ Property — reference User.emp_id
    # -----------------------------------------------------------
    @property
    def emp_id(self):
        """Access employee ID directly from linked User."""
        return getattr(self.user, "emp_id", None)

    # -----------------------------------------------------------
    # ✅ Validation
    # -----------------------------------------------------------
    def clean(self):
        """Ensure business rules and relational integrity."""
        if not self.user or not self.user.email:
            raise ValidationError({"user": "Linked User must have a valid email."})

        # Unique email check (one employee per user)
        if Employee.objects.exclude(id=self.id).filter(user__email=self.user.email).exists():
            raise ValidationError({"user": "An employee with this email already exists."})

        # Prevent self as manager
        if self.manager and self.manager == self:
            raise ValidationError({"manager": "An employee cannot be their own manager."})

        # Ensure manager has valid role
        if self.manager and self.manager.role not in ["Manager", "Admin"]:
            raise ValidationError({"manager": "Assigned manager must have role 'Manager' or 'Admin'."})

        # Department must be valid
        if not self.department:
            raise ValidationError({"department": "Employee must belong to a department."})

    # -----------------------------------------------------------
    # ✅ Save Override
    # -----------------------------------------------------------
    def save(self, *args, **kwargs):
        """Apply validation and update department employee count."""
        is_new = self.pk is None
        self.full_clean()

        # Save employee record
        super().save(*args, **kwargs)

        # Auto update department's employee count
        if self.department:
            self.department.update_employee_count()

        # If department changed, update old department count too
        if not is_new and hasattr(self, "_old_department_id"):
            old_dept = Department.objects.filter(id=self._old_department_id).first()
            if old_dept and old_dept != self.department:
                old_dept.update_employee_count()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_department_id = self.department_id

    # -----------------------------------------------------------
    # ✅ Display / Utility Methods
    # -----------------------------------------------------------
    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return f"{self.emp_id or '-'} - {full_name or self.user.username}"

    def get_full_name(self):
        """Return full name."""
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username

    def get_department_name(self):
        """Return readable department name."""
        return self.department.name if self.department else "-"

    def get_role_display_name(self):
        """Return readable role display."""
        return dict(self.ROLE_CHOICES).get(self.role, "Employee")
