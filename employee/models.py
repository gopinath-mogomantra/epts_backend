# ===============================================
# employee/models.py
# ===============================================
# Final Updated Version — Aligned with Section 2.2.1 (Employee Details)
# Includes minor best practices, constraints, and validation improvements
# ===============================================

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


# =====================================================
# ✅ DEPARTMENT MODEL
# =====================================================
class Department(models.Model):
    """
    Stores all departments in the organization.
    Example: HR, IT, Finance, Marketing.
    """
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


# =====================================================
# ✅ EMPLOYEE MODEL
# =====================================================
class Employee(models.Model):
    """
    Represents an employee entity linked to a user account.
    Stores HR-related information such as department, manager,
    designation, and employment status.
    """

    # Linked user account (contains username, email, emp_id, etc.)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        help_text="Linked user account for login and authentication",
    )

    # Department association
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        help_text="Department where the employee works",
    )

    # Self-referential manager relationship
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_members",
        help_text="Manager supervising this employee",
    )

    designation = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Job title or position",
    )

    # 📞 Contact number (added as per 2.2.1 requirement)
    contact_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(r"^\+?\d{7,15}$", "Enter a valid phone number.")],
        blank=True,
        null=True,
        help_text="Official contact number",
    )

    # Employment status
    status = models.CharField(
        max_length=20,
        choices=[
            ("Active", "Active"),
            ("On Leave", "On Leave"),
            ("Resigned", "Resigned"),
        ],
        default="Active",
        help_text="Employment status",
    )

    # 🗓️ Joining date
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
        """
        Human-readable representation of the employee.
        Example: "John Doe (EMP001)"
        """
        if hasattr(self, "user") and self.user:
            full_name = f"{self.user.first_name} {self.user.last_name}".strip()
            if not full_name:
                full_name = self.user.username
            return f"{full_name} ({self.user.emp_id})"
        return "Unassigned Employee"

    # -------------------------------------------------
    # 🔹 Model-level Validation
    # -------------------------------------------------
    def clean(self):
        """Prevent an employee from being assigned as their own manager."""
        if self.manager and self.manager_id == self.id:
            raise ValidationError("An employee cannot be their own manager.")

    # -------------------------------------------------
    # 🔹 Computed properties for easier access
    # -------------------------------------------------
    @property
    def emp_id(self):
        """Shortcut property to access the linked user's emp_id."""
        return getattr(self.user, "emp_id", None)

    @property
    def email(self):
        """Shortcut property to access the linked user's email."""
        return getattr(self.user, "email", None)

    @property
    def role(self):
        """Shortcut property to access the linked user's role."""
        return getattr(self.user, "role", None)

    @property
    def manager_name(self):
        """Returns the full name of the manager (if assigned)."""
        if self.manager and hasattr(self.manager, "user"):
            manager_user = self.manager.user
            full_name = f"{manager_user.first_name} {manager_user.last_name}".strip()
            return full_name or manager_user.username
        return "-"
