# ===============================================
# users/serializers.py
# ===============================================
# Handles:
# 1. JWT Token Serializer (Login)
# 2. User Registration (Admin/HR only)
# 3. Change Password (Authenticated users)
# 4. Profile Serializer (Read-only details)
# ===============================================

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
import random
import string

User = get_user_model()


# =====================================================
# ✅ 1. Custom JWT Token Serializer (Login)
# =====================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the JWT token payload to include user role, emp_id, and basic info.
    """

    username_field = "username"  # explicit field for clarity

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Embed user info into the token payload
        token["username"] = user.username
        token["email"] = user.email
        token["role"] = user.role
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        token["emp_id"] = user.emp_id
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Include user details in response body (not just token)
        data["user"] = {
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "role": self.user.role,
            "emp_id": self.user.emp_id,
        }
        return data


# =====================================================
# ✅ 2. User Registration Serializer
# =====================================================
class RegisterSerializer(serializers.ModelSerializer):
    """
    Used by Admins or HR to onboard new employees or managers.
    Auto-generates a secure password if not provided.
    """

    password = serializers.CharField(
        write_only=True, required=False, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "department",
            "phone",
            "role",
            "password",
            "password2",
            "joining_date",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        password = attrs.get("password")
        password2 = attrs.get("password2")

        if password or password2:
            if password != password2:
                raise serializers.ValidationError(
                    {"password": "Passwords do not match."}
                )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password", None)

        # ✅ Auto-generate random password if none provided
        if not password:
            password = "".join(
                random.choices(
                    string.ascii_letters + string.digits + "!@#$%^&*",
                    k=10,
                )
            )

        user = User.objects.create_user(password=password, **validated_data)

        # ⚠️ In production: Send the password to the user's official email securely
        return user


# =====================================================
# ✅ 3. Change Password Serializer
# =====================================================
class ChangePasswordSerializer(serializers.Serializer):
    """
    Enables any authenticated user to update their password.
    """

    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


# =====================================================
# ✅ 4. Profile Serializer (Read-Only)
# =====================================================
class ProfileSerializer(serializers.ModelSerializer):
    """
    Returns detailed, read-only profile info for authenticated users.
    """

    department_name = serializers.CharField(
        source="department.name", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "department",
            "department_name",
            "phone",
            "joining_date",
            "is_verified",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "emp_id",
            "username",
            "email",
            "role",
            "joining_date",
            "is_verified",
            "is_active",
            "department_name",
        ]
