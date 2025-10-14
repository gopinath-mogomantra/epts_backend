from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager for User model with superuser logic."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field is required.")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password or "Mogo@12345")
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create a superuser with default Admin role and null-safe department.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", "Admin")

        # Ensure superuser flags are correct
        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")

        # If department field exists but is required, set it to None explicitly
        extra_fields.setdefault("department", None)

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for EPTS (Employee Performance Tracking System).
    Supports role-based access and department linkage.
    """

    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Employee", "Employee"),
    ]

    emp_id = models.CharField(max_length=50, unique=True, help_text="Unique Employee ID")
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="Employee")
    phone = models.CharField(max_length=15, null=True, blank=True)

    # Department relation (nullable for superusers)
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    joining_date = models.DateField(default=timezone.now)
    is_verified = models.BooleanField(default=False, help_text="Set True after HR/email verification")

    # Django Auth flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Audit tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["emp_id"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["emp_id"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.emp_id})" if self.first_name else self.email

    # --- Role-based access helpers ---
    def is_admin(self):
        return self.role == "Admin" or self.is_superuser

    def is_manager(self):
        return self.role == "Manager"

    def is_employee(self):
        return self.role == "Employee"
