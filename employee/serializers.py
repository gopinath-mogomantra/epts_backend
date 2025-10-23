# ===============================================
# employee/serializers.py (Final Synced with emp_id-login system)
# ===============================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Department, Employee
import re

User = get_user_model()


# ===============================================================
# DEPARTMENT SERIALIZER
# ===============================================================
class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "employee_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "employee_count"]

    def get_employee_count(self, obj):
        return obj.employees.count()

    def validate_name(self, value):
        qs = Department.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A department with this name already exists.")
        return value.strip().title()

    def validate_is_active(self, value):
        if self.instance and not value:
            if Employee.objects.filter(department=self.instance, status="Active").exists():
                raise serializers.ValidationError("Cannot deactivate a department with active employees.")
        return value


# ===============================================================
# USER SUMMARY SERIALIZER (FOR ALL ROLES)
# ===============================================================
class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "role",
        ]

    def get_full_name(self, obj):
        first = obj.first_name or ""
        last = obj.last_name or ""
        return f"{first} {last}".strip()


# ===============================================================
# EMPLOYEE SERIALIZER (List / Detail)
# ===============================================================
class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    manager_name = serializers.SerializerMethodField(read_only=True)

    emp_id = serializers.ReadOnlyField(source="user.emp_id")
    first_name = serializers.ReadOnlyField(source="user.first_name")
    last_name = serializers.ReadOnlyField(source="user.last_name")
    full_name = serializers.ReadOnlyField(source="user.full_name")
    email = serializers.ReadOnlyField(source="user.email")
    role = serializers.ReadOnlyField(source="user.role")

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "emp_id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "contact_number",
            "department",
            "department_name",
            "role",
            "manager",
            "manager_name",
            "designation",
            "status",
            "joining_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_manager_name(self, obj):
        if obj.manager and obj.manager.user:
            first = obj.manager.user.first_name or ""
            last = obj.manager.user.last_name or ""
            return f"{first} {last}".strip()
        return None


# ===============================================================
# EMPLOYEE CREATE / UPDATE SERIALIZER
# ===============================================================
class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Create/Update Employee:
    - emp_id auto-generated and used as username
    - password auto-generated securely
    - department and manager editable
    """

    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)

    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=False,
    )
    manager = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        required=False,
        allow_null=True,
    )

    emp_id = serializers.ReadOnlyField(source="user.emp_id")

    class Meta:
        model = Employee
        fields = [
            "id",
            "email",
            "emp_id",
            "first_name",
            "last_name",
            "role",
            "contact_number",
            "department_id",
            "manager",
            "designation",
            "status",
            "joining_date",
        ]

    # =====================================================
    # FIELD VALIDATION
    # =====================================================
    def validate_first_name(self, value):
        if not re.match(r"^[A-Za-z ]+$", value):
            raise serializers.ValidationError("First name must contain only letters and spaces.")
        return value.strip().title()

    def validate_last_name(self, value):
        if not re.match(r"^[A-Za-z ]+$", value):
            raise serializers.ValidationError("Last name must contain only letters and spaces.")
        return value.strip().title()

    def validate_contact_number(self, value):
        """Ensure contact number is valid and unique."""
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Contact number must start with +91 and be a valid 10-digit Indian mobile number."
            )

        qs = Employee.objects.filter(contact_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This contact number is already assigned to another employee.")
        return value

    def validate_manager(self, value):
        if value and self.instance and value.id == self.instance.id:
            raise serializers.ValidationError("An employee cannot be their own manager.")
        if value and value.user.role != "Manager":
            raise serializers.ValidationError("Assigned manager must have a Manager role.")
        return value

    # =====================================================
    # CREATE
    # =====================================================
    def create(self, validated_data):
        department = validated_data.pop("department", None)
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        role = validated_data.pop("role")

        # 🔹 Create User (username auto-generated in UserManager)
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )

        # 🔹 Create linked Employee record
        employee = Employee.objects.create(user=user, department=department, **validated_data)
        return employee

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, instance, validated_data):
        department = validated_data.pop("department", None)
        if department:
            instance.department = department

        user = instance.user
        user_fields = ["email", "first_name", "last_name", "role"]
        for field in user_fields:
            if field in validated_data:
                setattr(user, field, validated_data.pop(field))
        user.save()

        allowed_fields = {
            "contact_number",
            "manager",
            "designation",
            "status",
            "joining_date",
        }
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)

        instance.save()
        return instance
