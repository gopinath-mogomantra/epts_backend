from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

class Role(models.Model):
    """
    Stores system roles like Admin, Manager, Employee.
    Used for controlling access levels in middleware and views.
    """
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.name

class CustomUser(AbstractUser):
    """
    Custom user model for Authentication & Role-Based Access module.

    Includes fields:
    - emp_id, role, joining_date
    - basic contact info for registration/profile
    - password handled by Django's built-in encryption
    """
    emp_id = models.CharField(max_length=50, unique=True, help_text="Unique Employee ID")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    joining_date = models.DateField(default=timezone.localdate)

    phone = models.CharField(max_length=15, null=True, blank=True)
    is_verified = models.BooleanField(default=False, help_text="Set to True after HR/email verification")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["emp_id"]

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return f"{full_name} ({self.emp_id})" if full_name else f"{self.username} ({self.emp_id})"

    # --- Helper methods for role-based access ---
    def is_admin(self):
        return (self.role and self.role.name.upper() == "ADMIN") or self.is_superuser

    def is_manager(self):
        return self.role and self.role.name.upper() == "MANAGER"

    def is_employee(self):
        return self.role and self.role.name.upper() == "EMPLOYEE"
