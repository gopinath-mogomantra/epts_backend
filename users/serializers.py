# ===========================================================
# users/serializers.py  (Final — Auto EmpID & Logged Temp Password)
# ===========================================================

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate, get_user_model
import random
import string
import logging

User = get_user_model()
logger = logging.getLogger("temp_password_logger")


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

        user = None
        if User.objects.filter(emp_id=login_input).exists():
            user = User.objects.get(emp_id=login_input)
        elif User.objects.filter(username=login_input).exists():
            user = User.objects.get(username=login_input)

        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        if user.account_locked:
            remaining = user.lock_remaining_time()
            if remaining:
                h, m = remaining["hours"], remaining["minutes"]
                raise serializers.ValidationError({
                    "detail": f"Account locked. Try again after {h}h {m}m."
                })
            else:
                user.unlock_account()

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

        user.reset_login_attempts()

        if getattr(user, "force_password_change", False):
            raise serializers.ValidationError({
                "force_password_change": True,
                "detail": "You must change your password before logging in."
            })

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
# ✅ REGISTER SERIALIZER (Auto EmpID + Temp Password + Logging)
# ===========================================================
class RegisterSerializer(serializers.ModelSerializer):
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
            "joining_date",
        ]
        read_only_fields = ["id", "emp_id"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()

    def create(self, validated_data):
        # 1️⃣ Auto-generate Emp ID
        last_user = User.objects.order_by('-id').first()
        if last_user and last_user.emp_id and last_user.emp_id.startswith("EMP"):
            try:
                last_num = int(last_user.emp_id.replace("EMP", ""))
            except ValueError:
                last_num = 0
        else:
            last_num = 0
        new_emp_id = f"EMP{last_num + 1:04d}"

        # 2️⃣ Auto-generate Secure Temp Password
        first_name = validated_data.get("first_name", "User").capitalize()
        random_part = "".join(random.choices(string.digits, k=4))
        temp_password = f"{first_name}@{random_part}"

        # 3️⃣ Create User
        user = User.objects.create_user(
            emp_id=new_emp_id,
            password=temp_password,
            **validated_data
        )

        # 4️⃣ Force password change at first login
        user.force_password_change = True
        user.save(update_fields=["force_password_change"])

        # 5️⃣ Log temp password (for testing)
        logger.info(
            f"Temp password created for {user.emp_id} ({user.username}, {user.email}) → {temp_password}"
        )

        # Attach password for API response
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
# ✅ PROFILE SERIALIZER
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
        read_only_fields = [
            "id",
            "emp_id",
            "joining_date",
            "is_verified",
            "is_active",
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()
    
    def get_joining_date(self, obj):
        """
        Ensures joining_date is serialized as a pure date even if it's a datetime object.
        """
        if obj.joining_date:
            # If joining_date has .date() (meaning it's datetime), convert to date
            return obj.joining_date.date() if hasattr(obj.joining_date, "date") else obj.joining_date
        return None
