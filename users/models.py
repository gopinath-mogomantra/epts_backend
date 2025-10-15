# ===========================================================
# users/models.py
# ===========================================================
# Custom user model for Employee Performance Tracking System (EPTS)
# Includes role-based access, linking with Department,
# and compatibility with Django Admin and JWT authentication.
# ===========================================================

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


# ===========================================================
# ✅ USER MANAGER
# ===========================================================
class UserManager(BaseUserManager):
    """Custom manager for User model with superuser creation logic."""

    def create_user(self, username, password=None, **extra_fields):
        """Create and save a regular user."""
        if not username:
            raise ValueError("The Username field is required.")

        extra_fields.setdefault("is_active", True)
        user = self.model(username=username, **extra_fields)
        user.set_password(password or "Mogo@12345")  # default password if not provided
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        """Create and save a superuser with Admin privileges."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "Admin")

        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(username, password, **extra_fields)


# ===========================================================
# ✅ USER MODEL
# ===========================================================
class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model used across the EPTS backend."""

    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Employee", "Employee"),
    ]

    emp_id = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique Employee ID (e.g., EMP001)",
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        help_text="Unique username for login",
    )
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="Employee")
    phone = models.CharField(max_length=15, null=True, blank=True)

    # ⚠ Avoid circular import: use string reference for Department model
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text="Linked department",
    )

    joining_date = models.DateField(default=timezone.now)
    is_verified = models.BooleanField(
        default=False,
        help_text="Set True after HR/email verification",
    )

    # Django Auth flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Audit tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"  # Used for login
    REQUIRED_FIELDS = ["emp_id", "email"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["emp_id"]

    def __str__(self):
        return f"{self.username} ({self.emp_id})"

    # ---------------------------------------------------
    # Helper Role Methods
    # ---------------------------------------------------
    def is_admin(self):
        return self.role == "Admin" or self.is_superuser

    def is_manager(self):
        return self.role == "Manager"

    def is_employee(self):
        return self.role == "Employee"
    