from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Department(models.Model):
    """
    Stores all departments within the organization.
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


class Employee(models.Model):
    """
    Employee model linked to CustomUser for personal details.
    Includes department, manager, role title, and status.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee_profile")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name="employees")
    manager = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="team_members")

    role_title = models.CharField(max_length=100, help_text="Job title or designation", default="Employee")
    joining_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[
        ("Active", "Active"),
        ("On Leave", "On Leave"),
        ("Resigned", "Resigned"),
    ], default="Active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name"]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.user.emp_id})"

    @property
    def manager_name(self):
        if self.manager:
            return f"{self.manager.user.first_name} {self.manager.user.last_name}"
        return None
