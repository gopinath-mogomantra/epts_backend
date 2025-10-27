# ===========================================================
# users/serializers.py (Production-Ready, Validated, API-Aligned)
# ===========================================================

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.utils import timezone
from django.core.validators import RegexValidator
import random
import string
import logging

User = get_user_model()
logger = logging.getLogger("users")


# ===========================================================
# ✅ LOGIN SERIALIZER (Custom JWT + Lockout Handling)
# ===========================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Handles login via emp_id or username.

    Features:
    - Login by emp_id or username
    - Account lockout after 5 failed attempts
    - Password-change enforcement
    - JWT token generation
    """

    username_field = "username"

    def validate(self, attrs):
        login_input = attrs.get("username")
        password = attrs.get("password")

        user = None
        # Lookup by emp_id or username
        if User.objects.filter(emp_id__iexact=login_input).exists():
            user = User.objects.get(emp_id__iexact=login_input)
        elif User.objects.filter(username__iexact=login_input).exists():
            user = User.objects.get(username__iexact=login_input)

        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        # Account locked?
        if user.account_locked:
            remaining = user.lock_remaining_time()
            if remaining:
                h, m = remaining["hours"], remaining["minutes"]
                raise serializers.ValidationError(
                    {"detail": f"Account locked. Try again after {h}h {m}m."}
                )
            else:
                user.unlock_account()

        # Authenticate
        authenticated_user = authenticate(username=user.emp_id, password=password)
        if not authenticated_user:
            user.increment_failed_attempts()
            remaining = max(0, user.LOCK_THRESHOLD - user.failed_login_attempts)
            if user.account_locked:
                raise serializers.ValidationError(
                    {"detail": f"Too many failed attempts. Account locked for {user.LOCK_DURATION_HOURS} hours."}
                )
            raise serializers.ValidationError(
                {"detail": f"Invalid credentials. {remaining} attempt(s) left."}
            )

        # Successful login
        user.reset_login_attempts()

        # Check if password change is required
        if getattr(user, "force_password_change", False):
            raise serializers.ValidationError({
                "force_password_change": True,
                "detail": "Password change required before login."
            })

        # Proceed with JWT generation
        data = super().validate({"username": user.emp_id, "password": password})
        data["user"] = {
            "id": user.id,
            "emp_id": user.emp_id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "department": user.department.name if user.department else None,
            "status": user.status,
            "is_verified": user.is_verified,
            "is_active": user.is_active,
        }
        return data


# ===========================================================
# ✅ REGISTER SERIALIZER (Atomic Create + Secure Temp Password)
# ===========================================================
class RegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    temp_password = serializers.CharField(read_only=True)

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
            "department_name",
            "phone",
            "role",
            "status",
            "joining_date",
            "temp_password",
        ]
        read_only_fields = ["id", "emp_id", "temp_password"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

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

    def validate_status(self, value):
        if value not in dict(User.STATUS_CHOICES):
            raise serializers.ValidationError("Invalid status.")
        return value

    def validate(self, attrs):
        """
        Only Admin or Manager can create users.
        """
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            if not request.user.is_admin() and not request.user.is_manager():
                raise serializers.ValidationError(
                    {"permission": "Only Admin or Manager can create users."}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """
        Create user with auto-generated emp_id and temporary password.
        """
        # Generate next emp_id safely
        last_user = User.objects.select_for_update().order_by("-id").first()
        last_num = 0
        if last_user and last_user.emp_id and last_user.emp_id.startswith("EMP"):
            try:
                last_num = int(last_user.emp_id.replace("EMP", ""))
            except ValueError:
                last_num = 0
        new_emp_id = f"EMP{last_num + 1:04d}"

        # Generate secure temporary password
        first_name = validated_data.get("first_name", "User").capitalize()
        random_part = "".join(random.choices(string.ascii_letters + string.digits, k=4))
        temp_password = f"{first_name}@{random_part}"

        user = User.objects.create_user(
            emp_id=new_emp_id,
            password=temp_password,
            **validated_data,
        )
        user.force_password_change = True
        user.save(update_fields=["force_password_change"])

        logger.info(
            "Temp password created for %s (%s) → %s",
            user.emp_id, user.email, temp_password,
        )

        # attach temp password for response
        user.temp_password = temp_password
        return user

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep["temp_password"] = getattr(instance, "temp_password", None)
        return rep


# ===========================================================
# ✅ CHANGE PASSWORD SERIALIZER
# ===========================================================
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)

    def validate_new_password(self, value):
        """
        Enforce strong password policy: at least 8 chars, 1 upper, 1 lower, 1 digit, 1 symbol.
        """
        import re
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

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.force_password_change = False
        user.save(update_fields=["password", "force_password_change"])
        logger.info("Password changed successfully for user %s", user.emp_id)
        return {"message": "Password changed successfully!"}


# ===========================================================
# ✅ PROFILE SERIALIZER (Self-Profile or Admin View)
# ===========================================================
class ProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    full_name = serializers.SerializerMethodField(read_only=True)
    joining_date = serializers.SerializerMethodField(read_only=True)

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
            "phone",
            "status",
            "joining_date",
            "is_verified",
            "is_active",
        ]
        read_only_fields = ["id", "emp_id", "joining_date", "is_verified", "is_active"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def get_joining_date(self, obj):
        if obj.joining_date:
            return obj.joining_date.date() if hasattr(obj.joining_date, "date") else obj.joining_date
        return None
