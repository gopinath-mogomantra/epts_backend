# ===========================================================
# employee/models.py ✅ Final — Soft Delete + Safe Manager Validation
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

    code = models.CharField(max_length=10, unique=True, help_text="Short department code (e.g., ENG01)")
    name = models.CharField(max_length=100, unique=True, help_text="Department name (e.g., Engineering)")
    description = models.TextField(blank=True, null=True, help_text="Optional department description.")
    employee_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        indexes = [models.Index(fields=["code"]), models.Index(fields=["name"])]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        """Ensure department code format is valid."""
        if not self.code.isalnum():
            raise ValidationError({"code": "Department code must be alphanumeric."})

    def update_employee_count(self):
        """Recalculate and update employee count."""
        self.employee_count = self.employees.filter(status="Active", is_deleted=False).count()
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
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="Employee")
    joining_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)

    # ✅ Soft Delete Flag
    is_deleted = models.BooleanField(default=False, help_text="Soft delete flag for employee.")

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
            models.Index(fields=["is_deleted"]),
        ]

    @property
    def emp_id(self):
        """Access employee ID directly from linked User."""
        return getattr(self.user, "emp_id", None)

    # -----------------------------------------------------------
    # ✅ Validation
    # -----------------------------------------------------------
    def clean(self):
        """Ensure business rules and relational integrity."""
        # Skip redundant clean if marked as serializer validated
        if hasattr(self, "_validated_from_serializer"):
            return

        # Deleted record cannot be modified
        if self.is_deleted:
            raise ValidationError({"employee": "❌ This employee record has been deleted. No modifications allowed."})

        if not self.user or not getattr(self.user, "email", None):
            raise ValidationError({"user": "Linked User must have a valid email."})

        # Duplicate email check
        if Employee.objects.exclude(id=self.id).filter(user__email=self.user.email).exists():
            raise ValidationError({"user": "An employee with this email already exists."})

        # Self-reference check
        if self.manager and self.manager == self:
            raise ValidationError({"manager": "An employee cannot be their own manager."})

        # Manager validity
        if self.manager:
            manager_role = getattr(self.manager.user, "role", None)
            if manager_role not in ["Manager", "Admin"]:
                raise ValidationError({"manager": ["Assigned manager must have role 'Manager' or 'Admin'."]})

        # Department validity
        if not self.department:
            raise ValidationError({"department": "Employee must belong to a department."})

        # Joining date validity
        if self.joining_date and self.joining_date > timezone.now().date():
            raise ValidationError({"joining_date": "Joining date cannot be in the future."})

    # -----------------------------------------------------------
    # ✅ Save Override
    # -----------------------------------------------------------
    def save(self, *args, **kwargs):
        """
        Apply validation and prevent operations on deleted employees.
        If already validated from serializer, skip redundant clean().
        """
        if self.is_deleted:
            raise ValidationError({"employee": "❌ Cannot modify a deleted employee."})

        try:
            if not hasattr(self, "_validated_from_serializer"):
                self.full_clean()
        except ValidationError as e:
            raise

        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Update department count
        if self.department:
            self.department.update_employee_count()

        # If department changed, update old department count
        if not is_new and hasattr(self, "_old_department_id"):
            old_dept = Department.objects.filter(id=self._old_department_id).first()
            if old_dept and old_dept != self.department:
                old_dept.update_employee_count()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._old_department_id = self.department_id

    # -----------------------------------------------------------
    # ✅ Soft Delete Logic
    # -----------------------------------------------------------
    def soft_delete(self):
        """Mark employee as deleted and deactivate user."""
        if self.is_deleted:
            raise ValidationError({"employee": "This employee is already deleted."})

        self.is_deleted = True
        self.status = "Inactive"

        if self.user:
            self.user.is_active = False
            self.user.save(update_fields=["is_active"])

        super().save(update_fields=["is_deleted", "status"])
        if self.department:
            self.department.update_employee_count()

    # -----------------------------------------------------------
    # ✅ Display / Utility
    # -----------------------------------------------------------
    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return f"{self.emp_id or '-'} - {full_name or self.user.username}"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username

    def get_department_name(self):
        return self.department.name if self.department else "-"

    def get_role_display_name(self):
        return dict(self.ROLE_CHOICES).get(self.role, "Employee")
