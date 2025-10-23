# ===========================================================
# users/models.py
# ===========================================================

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from datetime import timedelta


# ===========================================================
# USER MANAGER
# ===========================================================
class UserManager(BaseUserManager):
    """Custom manager for User model with emp_id-based login."""

    def generate_emp_id(self):
        """Generate the next available Employee ID like EMP0001, EMP0002, etc."""
        last_user = self.model.objects.order_by("-id").first()
        if last_user and last_user.emp_id and last_user.emp_id.startswith("EMP"):
            try:
                last_num = int(last_user.emp_id.replace("EMP", ""))
                return f"EMP{last_num + 1:04d}"
            except ValueError:
                pass
        return "EMP0001"

    def create_user(self, username=None, password=None, **extra_fields):
        import os
        from django.utils.crypto import get_random_string
        from datetime import datetime

        emp_id = extra_fields.get("emp_id") or self.generate_emp_id()
        username = emp_id

        if not password:
            password = get_random_string(
                length=12,
                allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+"
            )

        extra_fields["emp_id"] = emp_id
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.force_password_change = True  # ✅ Require password change after first login
        user.save(using=self._db)

        # Log credentials for development/testing
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "user_credentials.log")

        with open(log_file, "a") as f:
            f.write(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"emp_id: {emp_id} | username: {username} | temp_password: {password} | email: {extra_fields.get('email', 'N/A')}\n"
            )

        print(f"\n[USER CREATED] 👤 emp_id: {emp_id} | username: {username} | temp_password: {password}\n")
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "Admin")
        extra_fields.setdefault("is_active", True)
        return self.create_user(email=email, password=password, **extra_fields)


# ===========================================================
# USER MODEL
# ===========================================================
class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model used across the EPTS backend."""

    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Employee", "Employee"),
    ]

    emp_id = models.CharField(max_length=50, unique=True, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="Employee")

    phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        unique=True,
        validators=[RegexValidator(r"^\+?\d{7,15}$", "Enter a valid phone number.")]
    )

    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
    )

    joining_date = models.DateField(default=timezone.now)
    is_verified = models.BooleanField(default=False)

    # --------------------------------------------------------
    # Security & Account Management
    # --------------------------------------------------------
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    force_password_change = models.BooleanField(default=True)  # ✅ new field

    # Django auth flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # Audit tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "emp_id"
    REQUIRED_FIELDS = ["email", "username"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["emp_id"]
        indexes = [models.Index(fields=["username", "email", "emp_id"])]

    def __str__(self):
        return f"{self.username} ({self.emp_id})"

    # ---------------------------------------------------
    # Role helpers
    # ---------------------------------------------------
    def is_admin(self):
        return self.role == "Admin" or self.is_superuser

    def is_manager(self):
        return self.role == "Manager"

    def is_employee(self):
        return self.role == "Employee"

    # ---------------------------------------------------
    # Account Lockout Helpers
    # ---------------------------------------------------
    def lock_account(self):
        self.account_locked = True
        self.is_active = False
        self.locked_at = timezone.now()
        self.save(update_fields=["account_locked", "is_active", "locked_at"])

    def unlock_account(self):
        self.account_locked = False
        self.is_active = True
        self.failed_login_attempts = 0
        self.locked_at = None
        self.save(update_fields=["account_locked", "is_active", "failed_login_attempts", "locked_at"])

    def reset_login_attempts(self):
        if self.failed_login_attempts != 0:
            self.failed_login_attempts = 0
            self.save(update_fields=["failed_login_attempts"])

    def increment_failed_attempts(self):
        if self.account_locked and self.locked_at:
            if timezone.now() >= self.locked_at + timedelta(hours=2):
                self.unlock_account()

        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account()
        else:
            self.save(update_fields=["failed_login_attempts"])

    def lock_remaining_time(self):
        if not self.account_locked or not self.locked_at:
            return None
        remaining_seconds = (self.locked_at + timedelta(hours=2) - timezone.now()).total_seconds()
        if remaining_seconds <= 0:
            self.unlock_account()
            return None
        hours = int(remaining_seconds // 3600)
        minutes = int((remaining_seconds % 3600) // 60)
        return hours, minutes

    def require_password_change(self):
        """Return True if user must change password."""
        return self.force_password_change
