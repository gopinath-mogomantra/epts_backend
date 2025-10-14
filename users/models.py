from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager for User model."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password or "Mogo@12345")
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "Admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model used for authentication and role-based access.
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
    department = models.CharField(max_length=100, blank=True)
    joining_date = models.DateField(default=timezone.localdate)
    is_verified = models.BooleanField(default=False, help_text="Set True after HR/email verification")

    # Django auth defaults
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Audit
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
        return f"{self.first_name} {self.last_name} ({self.emp_id})" if self.first_name else f"{self.email}"

    # --- Role-based access helpers ---
    def is_admin(self):
        return self.role == "Admin" or self.is_superuser

    def is_manager(self):
        return self.role == "Manager"

    def is_employee(self):
        return self.role == "Employee"
