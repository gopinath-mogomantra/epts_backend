# ===========================================================
# users/serializers.py ✅ Final Frontend-Aligned & Signal-Free
# Employee Performance Tracking System (EPTS)
# ===========================================================

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.db import transaction, models
from django.utils import timezone
import random
import string
import logging
import re
from employee.models import Department

User = get_user_model()
logger = logging.getLogger("users")


# ===========================================================
# ✅ 1. LOGIN SERIALIZER (username / emp_id / email)
# ===========================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Safe and PK-secure login serializer.
    Supports username, emp_id, or email.
    Avoids Django authenticate() to prevent FK errors.
    """

    username_field = "username"
    LOCK_DURATION_HOURS = 2
    LOCK_THRESHOLD = 5

    def validate(self, attrs):
        login_input = attrs.get("username")
        password = attrs.get("password")

        if not login_input or not password:
            raise serializers.ValidationError(
                {"detail": "Both username (emp_id/username/email) and password are required."}
            )

        # Try to match user by username, emp_id, or email
        user = User.objects.filter(
            models.Q(username__iexact=login_input)
            | models.Q(emp_id__iexact=login_input)
            | models.Q(email__iexact=login_input)
        ).first()

        if not user:
            raise serializers.ValidationError({"detail": "Invalid username or password."})

        # Check account lock
        if user.account_locked:
            if user.locked_at:
                elapsed = timezone.now() - user.locked_at
                remaining_seconds = max(0, self.LOCK_DURATION_HOURS * 3600 - elapsed.total_seconds())
                if remaining_seconds > 0:
                    remaining_minutes = int(remaining_seconds // 60) % 60
                    remaining_hours = int(remaining_seconds // 3600)
                    raise serializers.ValidationError({
                        "detail": f"Account locked. Try again after {remaining_hours}h {remaining_minutes}m."
                    })
                else:
                    user.unlock_account()

        # ✅ Use check_password instead of authenticate() (bypasses USERNAME_FIELD issue)
        if not user.check_password(password):
            user.increment_failed_attempts()
            if user.account_locked:
                raise serializers.ValidationError({
                    "detail": f"Too many failed attempts. Account locked for {self.LOCK_DURATION_HOURS} hours."
                })
            remaining = max(0, self.LOCK_THRESHOLD - user.failed_login_attempts)
            raise serializers.ValidationError({"detail": f"Invalid credentials. {remaining} attempt(s) left."})

        # Reset failed attempts
        user.reset_login_attempts()

        # Enforce password change
        if user.force_password_change:
            raise serializers.ValidationError({
                "force_password_change": True,
                "detail": "Password change required before login."
            })

        # ✅ Manually create JWT since authenticate() is not used
        refresh = self.get_token(user)
        access = refresh.access_token

        data = {
            "refresh": str(refresh),
            "access": str(access),
            "user": {
                "id": user.id,
                "emp_id": user.emp_id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "department": user.department.name if user.department else None,
                "manager": user.manager.username if user.manager else None,
                "status": user.status,
                "is_verified": user.is_verified,
                "is_active": user.is_active,
            }
        }

        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["emp_id"] = user.emp_id
        token["role"] = user.role
        return token


# ===========================================================
# ✅ 2. REGISTER SERIALIZER (Signal-Free, Employee Sync)
# ===========================================================
class RegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    temp_password = serializers.CharField(read_only=True)

    department = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department_name_input = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    manager = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "department",
            "department_code",
            "department_name_input",
            "department_name",
            "manager",
            "phone",
            "role",
            "status",
            "joining_date",
            "temp_password",
        ]
        read_only_fields = ["id", "emp_id", "temp_password"]

    # ---------------- FULL NAME ----------------
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    # ---------------- VALIDATIONS ----------------
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_phone(self, value):
        if value and User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value

    def validate_role(self, value):
        if value not in dict(User.ROLE_CHOICES):
            raise serializers.ValidationError("Invalid role.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            if not request.user.is_admin() and not request.user.is_manager():
                raise serializers.ValidationError(
                    {"permission": "Only Admin or Manager can create users."}
                )
        return attrs

    # ---------------- CREATE USER ----------------
    @transaction.atomic
    def create(self, validated_data):
        from employee.models import Employee  # ✅ Safe import (avoids circular dependency)

        # Pop department/manager info
        dept_value = (
            validated_data.pop("department", None)
            or validated_data.pop("department_code", None)
            or validated_data.pop("department_name_input", None)
        )
        manager_value = validated_data.pop("manager", None)

        department_instance = None
        manager_instance = None

        # ✅ Resolve Department (code / name / id)
        if dept_value:
            dept_value = str(dept_value).strip()
            department_instance = Department.objects.filter(
                models.Q(code__iexact=dept_value)
                | models.Q(name__iexact=dept_value)
                | models.Q(id__iexact=dept_value)
            ).first()
            if not department_instance:
                raise serializers.ValidationError({
                    "department": f"Department '{dept_value}' not found. "
                                  f"Available: {[d.name for d in Department.objects.all()]}"
                })
        else:
            raise serializers.ValidationError({"department": "Department is required for Employees."})

        # ✅ Resolve Manager (emp_id or username)
        if manager_value:
            manager_instance = (
                User.objects.filter(emp_id__iexact=manager_value).first()
                or User.objects.filter(username__iexact=manager_value).first()
            )
            if not manager_instance:
                raise serializers.ValidationError({
                    "manager": f"No manager found matching '{manager_value}'."
                })

        # ✅ Generate new emp_id
        last_user = User.objects.select_for_update().order_by("-id").first()
        last_num = int(last_user.emp_id.replace("EMP", "")) if last_user and last_user.emp_id else 0
        new_emp_id = f"EMP{last_num + 1:04d}"

        # ✅ Temporary password
        first_name = validated_data.get("first_name", "User").capitalize()
        random_part = "".join(random.choices(string.ascii_letters + string.digits, k=4))
        temp_password = f"{first_name}@{random_part}"

        # ✅ Create User
        user = User.objects.create_user(
            emp_id=new_emp_id,
            password=temp_password,
            department=department_instance,
            manager=manager_instance,
            **validated_data,
        )
        user.force_password_change = True
        user.save(update_fields=["force_password_change"])

        # ✅ Create matching Employee record (replaces signal logic)
        Employee.objects.create(
            user=user,
            emp_id=user.emp_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            department=department_instance,
            manager=manager_instance,
        )

        # ✅ Attach temp password to serializer response
        user.temp_password = temp_password
        return user

    # ---------------- RESPONSE FORMAT ----------------
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["temp_password"] = getattr(instance, "temp_password", None)
        if instance.department:
            rep["department"] = instance.department.name
            rep["department_code"] = getattr(instance.department, "code", None)
        if instance.manager:
            rep["manager"] = instance.manager.username
        return rep


# ===========================================================
# ✅ 3. CHANGE PASSWORD SERIALIZER
# ===========================================================
# ===========================================================
# ✅ 3. CHANGE PASSWORD SERIALIZER (Enhanced with Confirm Password)
# ===========================================================
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_old_password(self, value):
        """Check if old password is correct."""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate_new_password(self, value):
        """Enforce strong password rules."""
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", value):
            raise serializers.ValidationError("Password must include at least one uppercase letter.")
        if not re.search(r"[a-z]", value):
            raise serializers.ValidationError("Password must include at least one lowercase letter.")
        if not re.search(r"\d", value):
            raise serializers.ValidationError("Password must include at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise serializers.ValidationError("Password must include at least one special character.")
        return value

    def validate(self, attrs):
        """Ensure new and confirm passwords match."""
        if attrs.get("new_password") != attrs.get("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "New password and confirmation do not match."})
        return attrs

    def save(self, **kwargs):
        """Change user password after validation."""
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.force_password_change = False
        user.save(update_fields=["password", "force_password_change"])
        logger.info(f"🔒 Password changed successfully for {user.emp_id}")
        return {"message": "✅ Password changed successfully!"}


# ===========================================================
# ✅ 4. PROFILE SERIALIZER
# ===========================================================
class ProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)
    joining_date = serializers.SerializerMethodField(read_only=True)
    manager = serializers.CharField(source="manager.username", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "department",
            "department_name",
            "manager",
            "phone",
            "status",
            "joining_date",
            "is_verified",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "emp_id",
            "username",
            "email",
            "full_name",
            "department_name",
            "manager",
            "joining_date",
            "is_verified",
            "is_active",
        ]

    # -------------------------------------------
    # Computed fields
    # -------------------------------------------
    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def get_joining_date(self, obj):
        if obj.joining_date:
            return obj.joining_date.date() if hasattr(obj.joining_date, "date") else obj.joining_date
        return None

    # -------------------------------------------
    # Safe update override
    # -------------------------------------------
    def update(self, instance, validated_data):
        editable_fields = [
            "first_name",
            "last_name",
            "department",
            "phone",
            "status",
            "role",
        ]
        for field in editable_fields:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        instance.save()
        return instance
