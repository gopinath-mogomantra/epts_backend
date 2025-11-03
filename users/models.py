# ===========================================================
# users/models.py
# ===========================================================

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models, transaction
from django.db.models import Max, Q
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import check_password, make_password
from datetime import timedelta, datetime
import uuid
import logging
import os
from django.db import connection

logger = logging.getLogger("users")


# ===========================================================
# PASSWORD HISTORY MODEL
# ===========================================================
class PasswordHistory(models.Model):
    """
    Track last 5 passwords to prevent reuse.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='password_history'
    )
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Password History"
        verbose_name_plural = "Password Histories"
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        # Avoid accessing user attributes that might not be fully saved in unusual cases.
        try:
            uname = getattr(self.user, 'username', None) or str(self.user_id)
        except Exception:
            uname = str(self.user_id)
        return f"{uname} - {self.created_at.strftime('%Y-%m-%d')}"

    @classmethod
    def add_password(cls, user, password_hash):
        """Store password hash, keep only the latest 5."""
        # Ensure the user has a PK before associating the history
        if not user.pk:
            return
        cls.objects.create(user=user, password_hash=password_hash)
        # Keep only the latest 5 entries
        old = cls.objects.filter(user=user).order_by('-created_at')[5:]
        if old:
            cls.objects.filter(id__in=[p.id for p in old]).delete()


# ===========================================================
# USER MANAGER
# ===========================================================
class UserManager(BaseUserManager):
    """Custom user manager handling secure emp_id generation."""

    def generate_emp_id(self):
        """Generate a unique emp_id in the format EMP0001, EMP0002, etc."""
        with transaction.atomic():
            table_name = self.model._meta.db_table

            with connection.cursor() as cursor:
                # Vendor-aware locking
                query = f"SELECT emp_id FROM {table_name} ORDER BY id DESC LIMIT 1"
                if connection.vendor == "postgresql":
                    query += " FOR UPDATE"
                cursor.execute(query)
                result = cursor.fetchone()

            if result and result[0]:
                try:
                    num = int(result[0].replace("EMP", ""))
                    return f"EMP{num + 1:04d}"
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid emp_id format found: {result[0]}")

            return "EMP0001"
        
    def create_user(self, username=None, password=None, **extra_fields):
        """Create a regular user with secure defaults and log temp password for testing."""
        emp_id = extra_fields.get("emp_id") or self.generate_emp_id()
        username = username or emp_id

        if not password:
            password = get_random_string(
                length=12,
                allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            )

        extra_fields["emp_id"] = emp_id
        extra_fields.setdefault("is_active", True)

        # Build user instance
        user = self.model(username=username, **extra_fields)
        # Use set_password so hashing + history logic works
        user.set_password(password)
        # store temp password in DB field (for development/testing only)
        user.temp_password = password

        # Save user
        user.save(using=self._db)

        # Log to local file for testing (safe, dev-only)
        try:
            # logs directory at project root (e.g. epts_backend/logs/)
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            log_dir = os.path.join(base_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, "temp_passwords.txt")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"{emp_id} - {getattr(user, 'email', '')} - {getattr(user, 'role', '')} - TempPassword: {password}\n"
                )
        except Exception as e:
            logger.warning(f"Failed to log temp password for {emp_id}: {e}")

        # Optional console output when DEBUG (helps live testing)
        try:
            from django.conf import settings
            if getattr(settings, "DEBUG", False):
                print(f"[TEMP-PASS] {emp_id} {getattr(user, 'email', '')} -> {password}")
        except Exception:
            pass

        logger.info(
            f"User created: {emp_id} (username: {username})",
            extra={'emp_id': emp_id, 'username': username, 'created_by': 'system'}
        )

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "Admin")
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("force_password_change", False)

        if not email:
            raise ValueError("Superuser must have an email.")
        if not password:
            raise ValueError("Superuser must have a password.")

        return self.create_user(email=email, password=password, **extra_fields)


# ===========================================================
# USER MODEL
# ===========================================================
class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for EPTS (Employee Performance Tracking System).
    Aligned with frontend forms and APIs.
    """

    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Employee", "Employee"),
    ]

    # ---------- CORE ----------
    emp_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Auto-generated employee ID (EMP0001, EMP0002, etc.)"
    )
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="Employee",
        db_index=True,
        help_text="User role"
    )

    temp_password = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Stores auto-generated temporary password for testing/logging."
    )

    # ---------- CONTACT ----------
    phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\+?\d{7,15}$", "Enter a valid phone number.")],
    )

    # ---------- ORGANIZATION ----------
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        limit_choices_to={'role__in': ['Manager', 'Admin']},
    )

    joining_date = models.DateField(default=timezone.now)

    # ---------- EMAIL VERIFICATION ----------
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, null=True, blank=True)
    verification_token_created = models.DateTimeField(null=True, blank=True)

    # ---------- SECURITY ----------
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    force_password_change = models.BooleanField(default=True)

    # ---------- DJANGO FLAGS ----------
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    # ---------- AUDIT ----------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---------- MANAGER ----------
    objects = UserManager()

    USERNAME_FIELD = "emp_id"
    REQUIRED_FIELDS = ["email", "username"]

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["emp_id"]
        indexes = [
            models.Index(fields=["username", "email", "emp_id"]),
            models.Index(fields=["role", "is_active"]),
        ]

    def __str__(self):
        # Keep __str__ lightweight and safe (avoid accessing FKs that may be problematic)
        try:
            full = self.get_full_name()
            return f"{full} ({self.emp_id})" if full else f"{self.username} ({self.emp_id})"
        except Exception:
            return f"{self.username or self.emp_id}"

    # ======================================================
    # BASIC METHODS
    # ======================================================
    def get_full_name(self):
        try:
            name = f"{self.first_name} {self.last_name}".strip()
            return name if name else self.username
        except Exception:
            return self.username

    def get_short_name(self):
        return self.first_name or self.username

    # ======================================================
    # VALIDATION
    # ======================================================
    def _check_circular_manager(self):
        """Check for circular manager references efficiently."""
        if not self.manager_id:
            return
        
        visited = {self.pk}
        current_id = self.manager_id
        
        # Use values_list to avoid loading full objects
        while current_id:
            if current_id in visited:
                raise ValidationError({
                    'manager': 'Circular manager relationship detected.'
                })
            visited.add(current_id)
            
            # Single query to get next manager ID
            next_manager_id = User.objects.filter(
                pk=current_id
            ).values_list('manager_id', flat=True).first()
            
            current_id = next_manager_id
            
            # Safety check: prevent infinite loops on bad data
            if len(visited) > 100:
                logger.error(f"Possible manager chain corruption for user {self.emp_id}")
                raise ValidationError({
                    'manager': 'Manager relationship chain is too deep.'
                })

    def clean(self):
        """Model-level validation."""
        super().clean()
        
        if self.role == "Employee" and not self.department_id:
            raise ValidationError({
                'department': 'Employees must belong to a department.'
            })
        
        if self.manager_id and self.pk:
            if self.manager_id == self.pk:
                raise ValidationError({
                    'manager': 'User cannot be their own manager.'
                })
            
            # Check for circular references
            self._check_circular_manager()

    def save(self, *args, **kwargs):
        """
        Save with safe validation: if object has a PK, run full_clean.
        If creating (no PK yet), run only light validation to avoid relationship access that requires PK.
        """
        # Light validation: we can still check certain constraints without forcing FK resolution
        # For create (no PK) call full_clean but tolerant: wrap in try/except to avoid FK lookups
        if self.pk:
            # On update, run full validation
            self.full_clean()
        else:
            # On create, run basic clean() but guard against FK problems
            try:
                # call clean() - it's guarded to avoid deep FK traversal if pk is missing
                self.clean()
            except ValidationError:
                # re-raise ValidationError so invalid data is not saved
                raise
            except Exception:
                # swallow other exceptions during create-time validation to avoid PK-related crashes;
                # let DB constraints report issues. This is defensive to avoid the PK relationship error.
                pass

        super().save(*args, **kwargs)

    # ======================================================
    # ACCOUNT STATUS & ROLE HELPERS
    # ======================================================
    @property
    def status(self):
        if self.account_locked:
            return "Locked"
        return "Active" if self.is_active else "Inactive"

    def is_admin(self):
        return self.role == "Admin" or self.is_superuser

    def is_manager(self):
        return self.role == "Manager"

    def is_employee(self):
        return self.role == "Employee"

    # ======================================================
    # ACCOUNT LOCKOUT & LOGIN ATTEMPTS
    # ======================================================
    @transaction.atomic
    def lock_account(self):
        """Lock user account due to failed login attempts."""
        self.account_locked = True
        self.is_active = False
        self.locked_at = timezone.now()
        self.save(update_fields=["account_locked", "is_active", "locked_at"])
        logger.warning(f"Account locked: {self.emp_id}")

    @transaction.atomic
    def unlock_account(self):
        """Unlock user account and reset failed attempts."""
        self.account_locked = False
        self.is_active = True
        self.failed_login_attempts = 0
        self.locked_at = None
        self.save(update_fields=[
            "account_locked", "is_active", "failed_login_attempts", "locked_at"
        ])
        logger.info(f"Account unlocked: {self.emp_id}")
        
    @transaction.atomic
    def increment_failed_attempts(self):
        """Safely increment failed login attempts with proper locking."""
        # Refresh from database with lock to prevent race conditions
        User.objects.filter(pk=self.pk).select_for_update().first()
        self.refresh_from_db(fields=['account_locked', 'locked_at', 'failed_login_attempts'])
        
        # Auto-unlock if lock period expired
        if self.account_locked and self.locked_at:
            lock_expiry = self.locked_at + timedelta(hours=2)
            if timezone.now() >= lock_expiry:
                self.unlock_account()
                return
        
        # Don't increment if already locked
        if self.account_locked:
            return
        
        # Use F() expression for atomic increment
        User.objects.filter(pk=self.pk).update(
            failed_login_attempts=models.F('failed_login_attempts') + 1
        )
        
        # Refresh to get the updated count
        self.refresh_from_db(fields=['failed_login_attempts'])
        
        # Lock account if threshold reached
        if self.failed_login_attempts >= 5:
            self.lock_account()
        
        logger.info(f"Failed login attempt for {self.emp_id}: {self.failed_login_attempts}/5")

    def reset_login_attempts(self):
        if self.failed_login_attempts > 0 or self.account_locked:
            self.failed_login_attempts = 0
            self.account_locked = False
            self.locked_at = None
            self.save(update_fields=["failed_login_attempts", "account_locked", "locked_at"])

    # ======================================================
    # PASSWORD MANAGEMENT
    # ======================================================
    def set_password(self, raw_password):
        """Set password with history check and proper validation."""
        
        # Check password history BEFORE setting
        if self.pk:
            recent_passwords = PasswordHistory.objects.filter(
                user=self
            ).order_by('-created_at')[:5]
            
            for old_pw in recent_passwords:
                try:
                    if check_password(raw_password, old_pw.password_hash):
                        raise ValidationError(
                            "Cannot reuse any of your last 5 passwords."
                        )
                except ValidationError:
                    raise  # Re-raise ValidationError
                except Exception as e:
                    # Log but continue - don't let corrupt history block password changes
                    logger.warning(
                        f"Error checking password history for {self.emp_id}: {e}"
                    )
                    continue
        
        # Set the password only if validation passed
        super().set_password(raw_password)
        
        # Add to password history
        if self.pk:
            try:
                new_hash = make_password(raw_password)
                PasswordHistory.add_password(self, new_hash)
            except Exception as e:
                # Log but don't fail the password set
                logger.error(
                    f"Failed to save password history for {self.emp_id}: {e}",
                    exc_info=True
                )

    def mark_password_changed(self):
        self.force_password_change = False
        self.save(update_fields=['force_password_change'])

    # ======================================================
    # EMAIL VERIFICATION
    # ======================================================
    def generate_verification_token(self):
        self.verification_token = str(uuid.uuid4())
        self.verification_token_created = timezone.now()
        # Save token fields without triggering deep validation
        self.save(update_fields=['verification_token', 'verification_token_created'])
        return self.verification_token

    def verify_email(self, token):
        # Validate token
        if not self.verification_token or self.verification_token != token:
            return False
        if not self.verification_token_created:
            return False
        if timezone.now() > self.verification_token_created + timedelta(hours=24):
            return False
        self.is_verified = True
        self.verification_token = None
        self.verification_token_created = None
        self.save(update_fields=['is_verified', 'verification_token', 'verification_token_created'])
        return True

