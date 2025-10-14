# ===============================================
# employee/models.py
# ===============================================
# Models: Department & Employee
# Integrated with the custom User model (username-based login)
# ===============================================

from django.db import models
from django.utils import timezone
from django.conf import settings

# Use settings.AUTH_USER_MODEL instead of importing get_user_model()
# to avoid potential circular import issues.
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

    # Link to the custom user model
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

    date_joined = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Employee"
        verbose_name_plural = "Employees"
        ordering = ["user__first_name"]

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
    # Computed properties for easier access
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
