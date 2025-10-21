# ===============================================
# users/serializers.py
# ===============================================
# Final Updated Version — JWT, Registration, Password, Profile
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

    username_field = "username"

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["email"] = user.email
        token["role"] = user.role
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        token["emp_id"] = user.emp_id
        token["is_verified"] = user.is_verified
        token["is_active"] = user.is_active
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "role": self.user.role,
            "emp_id": self.user.emp_id,
            "is_verified": self.user.is_verified,
            "is_active": self.user.is_active,
        }
        return data


# =====================================================
# ✅ 2. User Registration Serializer
# =====================================================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, validators=[validate_password])
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
                raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def validate_emp_id(self, value):
        if User.objects.filter(emp_id=value).exists():
            raise serializers.ValidationError("Employee ID already exists.")
        return value

    def create(self, validated_data):
        validated_data.pop("password2", None)
        password = validated_data.pop("password", None)
        if not password:
            password = "".join(random.choices(string.ascii_letters + string.digits + "!@#$%^&*", k=10))

        user = User.objects.create_user(password=password, **validated_data)
        return user


# =====================================================
# ✅ 3. Change Password Serializer
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
        user.save()
        return {"message": "Password updated successfully"}


# =====================================================
# ✅ 4. Profile Serializer (Read-Only)
# =====================================================
class ProfileSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    manager_name = serializers.SerializerMethodField()

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
            "manager_name",
            "phone",
            "joining_date",
            "is_verified",
            "is_active",
        ]
        read_only_fields = fields

    def get_manager_name(self, obj):
        if hasattr(obj, "employee_profile") and obj.employee_profile.manager:
            return str(obj.employee_profile.manager)
        return "-"
