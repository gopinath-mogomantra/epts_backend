# ===============================================
# employee/models.py
# ===============================================
# Basic setup for Employee & Department models
# Linked with your custom User model.
# ===============================================

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


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

    def __str__(self):
        return self.name


# =====================================================
# ✅ EMPLOYEE MODEL
# =====================================================
class Employee(models.Model):
    """
    Extends the User model with department and manager details.
    Basic HR profile for each employee.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee_profile"
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees"
    )

    # Optional: manager is another employee
    manager = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="team_members",
        help_text="Manager supervising this employee"
    )

    designation = models.CharField(max_length=100, blank=True, null=True, help_text="Job title or position")
    status = models.CharField(
        max_length=20,
        choices=[
            ("Active", "Active"),
            ("On Leave", "On Leave"),
            ("Resigned", "Resigned"),
        ],
        default="Active",
    )

    date_joined = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ["user__first_name"]

    def __str__(self):
        full_name = f"{self.user.first_name} {self.user.last_name}".strip()
        return f"{full_name} ({self.user.emp_id})"

    @property
    def manager_name(self):
        """Returns the full name of the manager (if any)."""
        if self.manager:
            return f"{self.manager.user.first_name} {self.manager.user.last_name}"
        return None

    @property
    def email(self):
        """Shortcut property to access user email easily."""
        return self.user.email

    @property
    def role(self):
        """Shortcut property to access user role easily."""
        return self.user.role
