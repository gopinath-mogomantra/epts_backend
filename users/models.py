# ===========================================================
# users/models.py  ✅ Frontend-Aligned + Production-Ready
# Employee Performance Tracking System (EPTS)
# ===========================================================

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from datetime import timedelta, datetime
import uuid
import os


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
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"

    @classmethod
    def add_password(cls, user, password_hash):
        """Store password hash, keep only latest 5."""
        cls.objects.create(user=user, password_hash=password_hash)
        old = cls.objects.filter(user=user)[5:]
        if old:
            cls.objects.filter(id__in=[p.id for p in old]).delete()


# ===========================================================
# USER MANAGER
# ===========================================================
class UserManager(BaseUserManager):
    """
    Custom manager for User model.
    Handles auto emp_id and secure password creation.
    """

    def generate_emp_id(self):
        with transaction.atomic():
            result = self.model.objects.select_for_update().aggregate(max_emp_id=Max('emp_id'))
            last_emp_id = result['max_emp_id']
            if last_emp_id and last_emp_id.startswith("EMP"):
                try:
                    num = int(last_emp_id.replace("EMP", ""))
                    return f"EMP{num + 1:04d}"
                except (ValueError, AttributeError):
                    pass
            return "EMP0001"

    def create_user(self, username=None, password=None, **extra_fields):
        """Create regular user aligned with frontend payload."""
        emp_id = extra_fields.get("emp_id") or self.generate_emp_id()
        username = username or emp_id

        if not password:
            password = get_random_string(
                length=12,
                allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            )

        extra_fields["emp_id"] = emp_id
        extra_fields.setdefault("is_active", True)

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        # Log basic info
        print(f"\n✅ [USER CREATED]")
        print(f"   emp_id: {emp_id}")
        print(f"   username: {username}")
        print(f"   temporary_password: {password}\n")

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create admin (superuser)."""
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
    Custom User model aligned with frontend fields:
    username, email, password, role, department, phone, manager
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

    username = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="Username for login"
    )

    email = models.EmailField(
        unique=True,
        db_index=True,
        help_text="User email address"
    )

    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="Employee",
        db_index=True,
        help_text="User role"
    )

    # ---------- CONTACT ----------
    phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\+?\d{7,15}$", "Enter a valid phone number.")],
        help_text="Optional phone number"
    )

    # ---------- ORGANIZATION ----------
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        help_text="Department of the user"
    )

    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='direct_reports',
        limit_choices_to={'role__in': ['Manager', 'Admin']},
        help_text="Reporting manager"
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
        return f"{self.username} ({self.emp_id})"

    # ---------- BASIC METHODS ----------
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def get_short_name(self):
        return self.first_name or self.username

    # ---------- VALIDATION ----------
    def clean(self):
        super().clean()
        if self.role == "Employee" and not self.department:
            raise ValidationError({'department': 'Employees must belong to a department.'})
        if self.manager and self.manager.id == self.id:
            raise ValidationError({'manager': 'User cannot be their own manager.'})

    # ---------- SAVE ----------
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    # ---------- STATUS ----------
    @property
    def status(self):
        if self.account_locked:
            return "Locked"
        return "Active" if self.is_active else "Inactive"

    # ---------- LOCKOUT ----------
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

    def increment_failed_attempts(self):
        if self.account_locked and self.locked_at:
            if timezone.now() >= self.locked_at + timedelta(hours=2):
                self.unlock_account()
                return
        if self.account_locked:
            return
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account()
        else:
            self.save(update_fields=["failed_login_attempts"])

    def reset_login_attempts(self):
        self.failed_login_attempts = 0
        self.account_locked = False
        self.locked_at = None
        self.save(update_fields=["failed_login_attempts", "account_locked", "locked_at"])

    # ---------- PASSWORD MANAGEMENT ----------
    def set_password(self, raw_password):
        from django.contrib.auth.hashers import check_password, make_password
        recent_passwords = self.password_history.all()[:5]
        for old_pw in recent_passwords:
            if check_password(raw_password, old_pw.password_hash):
                raise ValidationError("Cannot reuse last 5 passwords.")
        super().set_password(raw_password)
        if self.pk:
            PasswordHistory.add_password(self, make_password(raw_password))

    def mark_password_changed(self):
        self.force_password_change = False
        self.save(update_fields=['force_password_change'])

'''
# ===========================================================
# users/models.py - Development Ready & API Testing Ready
# Employee Performance Tracking System (EPTS)
# ===========================================================

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models, transaction
from django.db.models import Max
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from datetime import timedelta, datetime
from django.utils.crypto import get_random_string
import os
import uuid


# ===========================================================
# PASSWORD HISTORY MODEL
# ===========================================================
class PasswordHistory(models.Model):
    """
    Track password history to prevent password reuse.
    Business Rule: Users cannot reuse last 5 passwords.
    """
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='password_history'
    )
    password_hash = models.CharField(max_length=255)  # Store hashed password (never plain text!)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # Newest first
        verbose_name = "Password History"
        verbose_name_plural = "Password Histories"
        indexes = [
            models.Index(fields=['user', '-created_at']),  # Fast query for user's password history
        ]

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d')}"

    @classmethod
    def add_password(cls, user, password_hash):
        """
        Store password hash and keep only last 5 passwords.
        Called automatically when user changes password.
        """
        cls.objects.create(user=user, password_hash=password_hash)
        # Keep only last 5 passwords, delete older ones
        old_passwords = cls.objects.filter(user=user)[5:]
        if old_passwords:
            cls.objects.filter(id__in=[p.id for p in old_passwords]).delete()


# ===========================================================
# USER MANAGER
# ===========================================================
class UserManager(BaseUserManager):
    """
    Custom manager for User model.
    Handles user creation with auto-generated emp_id and secure passwords.
    """

    def generate_emp_id(self):
        """
        Generate next sequential Employee ID (EMP0001, EMP0002, etc).
        Thread-safe to prevent duplicate IDs when creating multiple users simultaneously.
        """
        with transaction.atomic():
            # Use select_for_update() to lock the table and prevent race conditions
            result = self.model.objects.select_for_update().aggregate(
                max_emp_id=Max('emp_id')
            )
            last_emp_id = result['max_emp_id']
            
            if last_emp_id and last_emp_id.startswith("EMP"):
                try:
                    # Extract number from "EMP0042" -> 42
                    num = int(last_emp_id.replace("EMP", ""))
                    # Increment and format: 43 -> "EMP0043"
                    return f"EMP{num + 1:04d}"
                except (ValueError, AttributeError):
                    pass
            
            # Default for first user
            return "EMP0001"

    def create_user(self, username=None, password=None, **extra_fields):
        """
        Create and save a regular user.
        - Auto-generates emp_id if not provided
        - Auto-generates secure password if not provided
        - Logs credentials to file (for development only!)
        """
        # Generate emp_id if not provided
        emp_id = extra_fields.get("emp_id") or self.generate_emp_id()
        username = username or emp_id

        # Generate secure random password if not provided
        if not password:
            password = get_random_string(
                length=12,
                allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
            )

        extra_fields["emp_id"] = emp_id
        extra_fields.setdefault("is_active", True)
        
        # Create user instance (not saved yet)
        user = self.model(username=username, **extra_fields)
        user.set_password(password)  # Hash password before saving

        # Only force password change if created by admin or password reset
        if extra_fields.get("is_reset", False):
            user.force_password_change = True
        else:
            user.force_password_change = False

        # Save to database
        user.save(using=self._db)

        # ✅ SECURE LOGGING - Only log non-sensitive information
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "user_creation.log")
        
        with open(log_file, "a") as f:
            f.write(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"emp_id: {emp_id} | username: {username} | "
                f"email: {extra_fields.get('email', 'N/A')} | "
                f"role: {extra_fields.get('role', 'Employee')} | "
                f"created_by: {extra_fields.get('created_by', 'system')}\n"
            )

        # ⚠️ DEVELOPMENT ONLY - Show password in console
        # TODO: Remove this in production or send via email
        print(f"\n✅ [USER CREATED]")
        print(f"   emp_id: {emp_id}")
        print(f"   username: {username}")
        print(f"   temporary_password: {password}")
        print(f"   ⚠️  Store this password securely!\n")
        
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a superuser (Admin).
        Required for: python manage.py createsuperuser
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "Admin")
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("force_password_change", False)  # Admin chooses their own password
        
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        
        return self.create_user(email=email, password=password, **extra_fields)


# ===========================================================
# USER MODEL
# ===========================================================
class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for EPTS (Employee Performance Tracking System).
    
    Business Rules:
    - emp_id is unique and auto-generated (EMP0001, EMP0002, etc.)
    - emp_id is used for login (not username)
    - Employees must have a department
    - Managers can have direct reports
    - Account locks after 5 failed login attempts (for 2 hours)
    - Users must change password if force_password_change=True
    """

    ROLE_CHOICES = [
        ("Admin", "Admin"),        # Full system access
        ("Manager", "Manager"),    # Can manage team members
        ("Employee", "Employee"),  # Regular employee
    ]

    # ============================================
    # CORE FIELDS
    # ============================================
    emp_id = models.CharField(
        max_length=50, 
        unique=True, 
        editable=False,  # Cannot be edited after creation
        db_index=True,   # Index for fast login queries
        help_text="Auto-generated employee ID (EMP0001, EMP0002, etc.)"
    )
    
    username = models.CharField(
        max_length=150, 
        unique=True, 
        db_index=True,
        help_text="Username for display purposes"
    )
    
    email = models.EmailField(
        unique=True, 
        db_index=True,
        help_text="Employee email address"
    )
    
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default="Employee",
        db_index=True,  # Index for role-based queries
        help_text="User role in the system"
    )

    # ============================================
    # CONTACT INFORMATION
    # ============================================
    phone = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        validators=[RegexValidator(
            r"^\+?\d{7,15}$", 
            "Enter a valid phone number (7-15 digits, optional + prefix)"
        )],
        help_text="Optional phone number"
    )

    # ============================================
    # ORGANIZATIONAL STRUCTURE
    # ============================================
    department = models.ForeignKey(
        "employee.Department",
        on_delete=models.PROTECT,  # Cannot delete department if users assigned
        null=True,
        blank=True,
        related_name="users",
        help_text="Employee's department"
    )
    
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,  # If manager deleted, set to NULL
        null=True,
        blank=True,
        related_name='direct_reports',
        limit_choices_to={'role__in': ['Manager', 'Admin']},  # Only managers can be assigned
        help_text="Immediate reporting manager"
    )

    # ============================================
    # DATES
    # ============================================
    joining_date = models.DateField(
        default=timezone.now,
        help_text="Date when employee joined"
    )

    # ============================================
    # EMAIL VERIFICATION
    # ============================================
    is_verified = models.BooleanField(
        default=False,
        help_text="Email verification status"
    )
    verification_token = models.CharField(
        max_length=100, 
        null=True, 
        blank=True,
        help_text="Token for email verification"
    )
    verification_token_created = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When verification token was created"
    )

    # ============================================
    # SECURITY & ACCOUNT LOCKOUT
    # ============================================
    failed_login_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of consecutive failed login attempts"
    )
    account_locked = models.BooleanField(
        default=False,
        help_text="Whether account is locked due to failed attempts"
    )
    locked_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When account was locked"
    )
    force_password_change = models.BooleanField(
        default=True,
        help_text="User must change password on next login"
    )

    # ============================================
    # DJANGO AUTH FLAGS
    # ============================================
    is_active = models.BooleanField(
        default=True,
        help_text="User can login if True"
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="User can access admin site if True"
    )
    date_joined = models.DateTimeField(auto_now_add=True)

    # ============================================
    # AUDIT FIELDS
    # ============================================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ============================================
    # MANAGER & AUTH CONFIGURATION
    # ============================================
    objects = UserManager()

    USERNAME_FIELD = "emp_id"  # Use emp_id for login
    REQUIRED_FIELDS = ["email", "username"]  # Required when creating superuser

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["emp_id"]
        indexes = [
            models.Index(fields=["username", "email", "emp_id"]),
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["department", "role"]),
        ]
        # Unique phone constraint (only when not null/empty)
        constraints = [
            models.UniqueConstraint(
                fields=['phone'],
                condition=models.Q(phone__isnull=False) & ~models.Q(phone=''),
                name='unique_phone_when_not_null'
            )
        ]

    def __str__(self):
        return f"{self.get_full_name()} ({self.emp_id})"

    # ============================================
    # BASIC METHODS
    # ============================================
    def get_full_name(self):
        """Return full name or username if name not set."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username

    def get_short_name(self):
        """Return first name or username."""
        return self.first_name if self.first_name else self.username

    # ============================================
    # VALIDATION
    # ============================================
    def clean(self):
        """
        Model-level validation.
        Called before save() if you use full_clean().
        """
        super().clean()
        
        # Business Rule: Employees must have a department
        if self.role == "Employee" and not self.department:
            raise ValidationError({
                'department': 'Employees must be assigned to a department.'
            })
        
        # Business Rule: User cannot be their own manager
        if self.manager and self.manager.id == self.id:
            raise ValidationError({
                'manager': 'User cannot be their own manager.'
            })
        
        # Business Rule: Check for circular manager relationships
        if self.manager:
            current_manager = self.manager
            visited = {self.id}
            while current_manager:
                if current_manager.id in visited:
                    raise ValidationError({
                        'manager': 'Circular manager relationship detected.'
                    })
                visited.add(current_manager.id)
                current_manager = current_manager.manager

    def save(self, *args, **kwargs):
        """
        Override save to add business logic validation.
        """
        # Check if role is changing from Manager/Admin to Employee
        if self.pk:
            try:
                old_user = User.objects.get(pk=self.pk)
                # Business Rule: Cannot demote manager who has direct reports
                if old_user.role in ["Manager", "Admin"] and self.role == "Employee":
                    if self.direct_reports.exists():
                        raise ValidationError(
                            "Cannot change role from Manager/Admin. Reassign direct reports first."
                        )
            except User.DoesNotExist:
                pass
        
        # Run full validation
        self.full_clean()
        super().save(*args, **kwargs)

    # ============================================
    # PROPERTIES
    # ============================================
    @property
    def status(self):
        """
        Dynamic status based on account state.
        Used by frontend for display.
        """
        if self.account_locked:
            return "Locked"
        return "Active" if self.is_active else "Inactive"

    # ============================================
    # ROLE HELPER METHODS
    # ============================================
    def is_admin(self):
        """Check if user is admin."""
        return self.role == "Admin" or self.is_superuser

    def is_manager(self):
        """Check if user is manager."""
        return self.role == "Manager"

    def is_employee(self):
        """Check if user is employee."""
        return self.role == "Employee"

    # ============================================
    # MANAGER HIERARCHY METHODS
    # ============================================
    def get_all_subordinates(self):
        """
        Get all employees under this manager recursively.
        Returns QuerySet of all subordinates (including subordinates of subordinates).
        
        Example:
        VP Engineering
        ├── Manager A
        │   ├── Dev 1
        │   └── Dev 2
        └── Manager B
            └── Dev 3
        
        VP.get_all_subordinates() returns: [Manager A, Dev 1, Dev 2, Manager B, Dev 3]
        """
        if not self.is_manager() and not self.is_admin():
            return User.objects.none()
        
        # Get direct reports
        subordinates = list(self.direct_reports.all())
        all_subordinates = subordinates.copy()
        
        # Recursively get subordinates of subordinates
        for subordinate in subordinates:
            if subordinate.is_manager() or subordinate.is_admin():
                all_subordinates.extend(subordinate.get_all_subordinates())
        
        # Return as QuerySet for further filtering
        return User.objects.filter(id__in=[s.id for s in all_subordinates])

    def get_manager_chain(self):
        """
        Get the full management chain up to top level.
        Returns list of managers from immediate to CEO.
        
        Example:
        Dev -> Team Lead -> Manager -> VP -> CEO
        Returns: [Team Lead, Manager, VP, CEO]
        """
        chain = []
        current_manager = self.manager
        visited = set()
        
        while current_manager and current_manager.id not in visited:
            chain.append(current_manager)
            visited.add(current_manager.id)
            current_manager = current_manager.manager
        
        return chain

    # ============================================
    # ACCOUNT LOCKOUT METHODS
    # ============================================
    def lock_account(self):
        """
        Lock account for 2 hours after repeated failed login attempts.
        Business Rule: Auto-lock after 5 failed attempts.
        """
        self.account_locked = True
        self.is_active = False
        self.locked_at = timezone.now()
        self.save(update_fields=["account_locked", "is_active", "locked_at"])

    def unlock_account(self):
        """
        Unlock account manually or automatically after lock period.
        Resets failed login attempts counter.
        """
        self.account_locked = False
        self.is_active = True
        self.failed_login_attempts = 0
        self.locked_at = None
        self.save(update_fields=["account_locked", "is_active", "failed_login_attempts", "locked_at"])

    def increment_failed_attempts(self):
        """
        Increment failed login attempts counter.
        Auto-locks account if threshold reached (5 attempts).
        Auto-unlocks if lock period expired (2 hours).
        """
        # Check if account should be auto-unlocked
        if self.account_locked and self.locked_at:
            if timezone.now() >= self.locked_at + timedelta(hours=2):
                self.unlock_account()
                return  # Exit after unlocking
        
        # Don't increment if already locked
        if self.account_locked:
            return
        
        # Increment counter
        self.failed_login_attempts += 1
        
        # Lock account if threshold reached
        if self.failed_login_attempts >= 5:
            self.lock_account()
        else:
            self.save(update_fields=["failed_login_attempts"])

    def reset_login_attempts(self):
        """
        Reset failed login attempts after successful login.
        Called by authentication backend.
        """
        if self.failed_login_attempts != 0 or self.account_locked:
            self.failed_login_attempts = 0
            self.account_locked = False
            self.locked_at = None
            self.save(update_fields=["failed_login_attempts", "account_locked", "locked_at"])

    def lock_remaining_time(self):
        """
        Return remaining lock time in human-readable format.
        Returns: dict with hours, minutes, total_seconds or None if not locked.
        
        Example: {'hours': 1, 'minutes': 30, 'total_seconds': 5400}
        """
        if not self.account_locked or not self.locked_at:
            return None
        
        remaining_seconds = (self.locked_at + timedelta(hours=2) - timezone.now()).total_seconds()
        
        # Auto-unlock if time expired
        if remaining_seconds <= 0:
            self.unlock_account()
            return None
        
        hours = int(remaining_seconds // 3600)
        minutes = int((remaining_seconds % 3600) // 60)
        
        return {
            'hours': hours,
            'minutes': minutes,
            'total_seconds': int(remaining_seconds)
        }

    # ============================================
    # EMAIL VERIFICATION METHODS
    # ============================================
    def generate_verification_token(self):
        """
        Generate email verification token valid for 24 hours.
        Returns the token for use in verification email.
        
        Usage:
        user = User.objects.get(email='test@example.com')
        token = user.generate_verification_token()
        # Send email with verification link: /verify-email/?token={token}
        """
        self.verification_token = str(uuid.uuid4())
        self.verification_token_created = timezone.now()
        self.save(update_fields=['verification_token', 'verification_token_created'])
        return self.verification_token

    def verify_email(self, token):
        """
        Verify email with token.
        Returns: True if successful, False otherwise.
        
        Usage:
        if user.verify_email(request.GET.get('token')):
            return "Email verified successfully"
        else:
            return "Invalid or expired token"
        """
        # Check if token matches
        if not self.verification_token or self.verification_token != token:
            return False
        
        # Check if token expired (24 hours)
        if timezone.now() > self.verification_token_created + timedelta(hours=24):
            return False
        
        # Mark as verified
        self.is_verified = True
        self.verification_token = None
        self.verification_token_created = None
        self.save(update_fields=['is_verified', 'verification_token', 'verification_token_created'])
        return True

    def is_verification_token_expired(self):
        """
        Check if verification token has expired (24 hours).
        Returns: True if expired or doesn't exist, False if still valid.
        """
        if not self.verification_token_created:
            return True
        return timezone.now() > self.verification_token_created + timedelta(hours=24)

    # ============================================
    # PASSWORD MANAGEMENT
    # ============================================
    def set_password(self, raw_password):
        """
        Override to check password history and prevent reuse.
        Business Rule: Cannot reuse last 5 passwords.
        
        Raises ValidationError if password was recently used.
        """
        from django.contrib.auth.hashers import check_password, make_password
        
        # Check against last 5 passwords
        recent_passwords = self.password_history.all()[:5]
        for old_pw in recent_passwords:
            if check_password(raw_password, old_pw.password_hash):
                raise ValidationError(
                    "Cannot reuse any of your last 5 passwords. Please choose a different password."
                )
        
        # Set the new password (hashed)
        super().set_password(raw_password)
        
        # Store in password history (only if user exists in DB)
        if self.pk:
            PasswordHistory.add_password(self, make_password(raw_password))

    def require_password_change(self):
        """
        Check if user must change password at next login.
        Returns: True if password change required, False otherwise.
        """
        return self.force_password_change

    def mark_password_changed(self):
        """
        Mark that user has changed their password.
        Call this after successful password change.
        """
        self.force_password_change = False
        self.save(update_fields=['force_password_change'])
'''