# ===========================================================
# users/serializers.py 
# ===========================================================

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
import random
import string

User = get_user_model()


# ===========================================================
# ✅ LOGIN SERIALIZER (Custom JWT)
# ===========================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Handles login via emp_id or username.
    Includes:
    - Account lockout (after 5 failed attempts)
    - Password change enforcement
    - JWT token generation
    """

    username_field = "username"

    def validate(self, attrs):
        login_input = attrs.get("username")
        password = attrs.get("password")

        # Try login via emp_id or username
        user = None
        if User.objects.filter(emp_id=login_input).exists():
            user = User.objects.get(emp_id=login_input)
        elif User.objects.filter(username=login_input).exists():
            user = User.objects.get(username=login_input)

        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        # Check lockout
        if user.account_locked:
            remaining = user.lock_remaining_time()
            if remaining:
                h, m = remaining["hours"], remaining["minutes"]
                raise serializers.ValidationError({
                    "detail": f"Account locked. Try again after {h}h {m}m."
                })
            else:
                user.unlock_account()

        # Authenticate using emp_id
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

        # Reset attempts
        user.reset_login_attempts()

        # Check for force password change
        if getattr(user, "force_password_change", False):
            raise serializers.ValidationError({
                "force_password_change": True,
                "detail": "You must change your password before logging in."
            })

        # Generate JWT
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
# ✅ REGISTRATION SERIALIZER
# ===========================================================
class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles new user registration.
    - emp_id auto-generated
    - Optional password (auto-random if not provided)
    - Includes password confirmation for frontend validation
    """

    password = serializers.CharField(write_only=True, required=False)
    password2 = serializers.CharField(write_only=True, required=False)
    full_name = serializers.SerializerMethodField(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

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
            "password",
            "password2",
            "joining_date",
        ]
        read_only_fields = ["id", "emp_id"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def validate(self, attrs):
        password = attrs.get("password")
        password2 = attrs.get("password2")
        if password or password2:
            if password != password2:
                raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password", None)

        # Auto-generate secure password if not provided
        if not password:
            password = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=10))

        user = User.objects.create_user(password=password, **validated_data)
        return user


# ===========================================================
# ✅ CHANGE PASSWORD SERIALIZER
# ===========================================================
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.force_password_change = False
        user.save()
        return {"message": "Password changed successfully!"}


# ===========================================================
# ✅ PROFILE SERIALIZER (Read-Only)
# ===========================================================
class ProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
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
            "phone",
            "status",
            "joining_date",
            "is_verified",
            "is_active",
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()
