# ===============================================
# users/serializers.py  (Final Synced Version)
# ===============================================

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
import random
import string

User = get_user_model()


# =====================================================
# ✅ Custom JWT Token Serializer (Login)
# =====================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom login serializer allowing login via emp_id or username.
    Includes:
    - Account lockout (5 failed attempts → 2 hr lock)
    - Force password change enforcement
    - JWT token generation
    """

    username_field = "username"  # frontend still sends "username"

    def validate(self, attrs):
        login_input = attrs.get("username")
        password = attrs.get("password")

        # 🔹 Try finding user by emp_id or username
        user = None
        if User.objects.filter(emp_id=login_input).exists():
            user = User.objects.get(emp_id=login_input)
        elif User.objects.filter(username=login_input).exists():
            user = User.objects.get(username=login_input)

        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        # 🔹 Check lockout status
        if user.account_locked:
            remaining = user.lock_remaining_time()
            if remaining:
                h, m = remaining
                raise serializers.ValidationError({
                    "detail": f"Account locked. Try again after {h}h {m}m."
                })
            else:
                user.unlock_account()

        # 🔹 Authenticate using emp_id (USERNAME_FIELD)
        authenticated_user = authenticate(username=user.emp_id, password=password)
        if not authenticated_user:
            user.increment_failed_attempts()
            remaining = max(0, 5 - user.failed_login_attempts)
            if user.account_locked:
                raise serializers.ValidationError({
                    "detail": "Too many failed attempts. Account locked for 2 hours."
                })
            raise serializers.ValidationError({
                "detail": f"Invalid credentials. {remaining} attempts left."
            })

        # 🔹 Reset login attempts after success
        user.reset_login_attempts()

        # 🔹 Force password change logic
        if getattr(user, "force_password_change", False):
            raise serializers.ValidationError({
                "force_password_change": True,
                "detail": "You must change your password before logging in."
            })

        # 🔹 Generate JWT tokens
        data = super().validate({"username": user.emp_id, "password": password})
        data["user"] = {
            "id": user.id,
            "emp_id": user.emp_id,
            "username": user.username,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_verified": user.is_verified,
            "is_active": user.is_active,
        }
        return data


# =====================================================
# ✅ User Registration Serializer
# =====================================================
class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles user registration.
    - emp_id auto-generated
    - Optional password (auto-random if not provided)
    - Includes password confirmation
    """

    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=False)
    full_name = serializers.SerializerMethodField(read_only=True)

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
            "phone",
            "role",
            "password",
            "password2",
            "joining_date",
        ]
        read_only_fields = ["id", "emp_id"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def validate(self, attrs):
        """Ensure password confirmation matches."""
        password = attrs.get("password")
        password2 = attrs.get("password2")

        if password or password2:
            if password != password2:
                raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        """Auto-generate emp_id, username, and password if needed."""
        validated_data.pop("password2", None)
        password = validated_data.pop("password", None)
        if not password:
            password = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=10))
        return User.objects.create_user(password=password, **validated_data)


# =====================================================
# ✅ Change Password Serializer
# =====================================================
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.force_password_change = False  # ✅ clear force flag after change
        user.save()
        return {"message": "✅ Password changed successfully!"}


# =====================================================
# ✅ Profile Serializer (Read-Only)
# =====================================================
class ProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    manager_name = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField(read_only=True)

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
            "manager_name",
            "phone",
            "joining_date",
            "is_verified",
            "is_active",
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def get_manager_name(self, obj):
        """Safely get manager name if employee is linked."""
        if hasattr(obj, "employee_profile") and obj.employee_profile.manager:
            mgr = obj.employee_profile.manager.user
            return f"{mgr.first_name} {mgr.last_name}".strip()
        return "-"
