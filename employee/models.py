# ===============================================
# employee/models.py
# ===============================================
# Final Updated Version — Safe and Conflict-Free
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
    """Stores all departments in the organization (HR, IT, etc.)"""
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
    """Represents an employee linked to a user account with department, manager, and role details."""

    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Employee", "Employee"),
    ]

    # 🔹 Core Fields
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="Employee",
        help_text="Defines whether the employee is an Admin, Manager, or Employee.",
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        help_text="Linked user account for login and authentication.",
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
        help_text="Manager supervising this employee.",
    )

    designation = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Job title or position (e.g., Developer, Team Lead).",
    )

    # 📞 Contact Number Validation: +91 followed by 10 digits
    contact_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                r"^\+91[6-9]\d{9}$",
                "Contact number must start with +91 and be a valid 10-digit Indian mobile number.",
            )
        ],
        blank=True,
        null=True,
        help_text="Official contact number.",
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("Active", "Active"),
            ("On Leave", "On Leave"),
            ("Resigned", "Resigned"),
        ],
        default="Active",
        help_text="Employment status.",
    )

    joining_date = models.DateField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -------------------------------------------------
    # 🔹 Meta Info
    # -------------------------------------------------
    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ["user__first_name"]
        indexes = [
            models.Index(fields=["department"]),
            models.Index(fields=["manager"]),
            models.Index(fields=["status"]),
        ]

    # -------------------------------------------------
    # 🔹 String Representation
    # -------------------------------------------------
    def __str__(self):
        """Human-readable representation."""
        if hasattr(self, "user") and self.user:
            full_name = f"{self.user.first_name} {self.user.last_name}".strip()
            if not full_name:
                full_name = self.user.username
            return f"{full_name} ({getattr(self.user, 'emp_id', 'No ID')})"
        return "Unassigned Employee"

    # -------------------------------------------------
    # 🔹 Validation
    # -------------------------------------------------
    def clean(self):
        """Prevent an employee from being assigned as their own manager."""
        if self.manager and self.manager_id == self.id:
            raise ValidationError("An employee cannot be their own manager.")

    # -------------------------------------------------
    # 🔹 Computed Properties
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
    def user_role(self):
        """Access role of linked user (if stored separately)."""
        return getattr(self.user, "role", None)

    @property
    def manager_name(self):
        """Returns the full name of the manager (if assigned)."""
        if self.manager and hasattr(self.manager, "user"):
            manager_user = self.manager.user
            full_name = f"{manager_user.first_name} {manager_user.last_name}".strip()
            return full_name or manager_user.username
        return "-"
