# ===============================================
# employee/serializers.py (Business-Ready — 2025-10-24)
# ===============================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Department, Employee
import re

User = get_user_model()

# ===============================================================
# ✅ DEPARTMENT SERIALIZER
# ===============================================================
class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id", "code", "name", "description", "is_active",
            "employee_count", "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at", "employee_count"]

    def get_employee_count(self, obj):
        return obj.employees.count()

    def validate_name(self, value):
        qs = Department.objects.filter(name__iexact=value, is_active=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department with this name already exists.")
        return value.strip().title()

    def validate_code(self, value):
        qs = Department.objects.filter(code__iexact=value, is_active=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department with this code already exists.")
        return value.strip().upper()

    def validate_is_active(self, value):
        if self.instance and not value:
            if Employee.objects.filter(department=self.instance, status="Active").exists():
                raise serializers.ValidationError("Cannot deactivate a department with active employees.")
        return value


# ===============================================================
# ✅ USER SUMMARY SERIALIZER
# ===============================================================
class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


# ===============================================================
# ✅ EMPLOYEE SERIALIZER (List / Detail)
# ===============================================================
class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    department_code = serializers.ReadOnlyField(source="department.code")
    manager_name = serializers.ReadOnlyField(read_only=True)
    reporting_to = serializers.ReadOnlyField(source="reporting_to_name")

    emp_id = serializers.ReadOnlyField(source="user.emp_id")
    first_name = serializers.ReadOnlyField(source="user.first_name")
    last_name = serializers.ReadOnlyField(source="user.last_name")
    full_name = serializers.SerializerMethodField(read_only=True)
    email = serializers.ReadOnlyField(source="user.email")
    role = serializers.ReadOnlyField(source="user.role")

    class Meta:
        model = Employee
        fields = [
            "id", "user", "emp_id", "first_name", "last_name", "full_name", "email",
            "contact_number", "department", "department_name", "department_code",
            "role", "manager", "manager_name", "reporting_to", "designation",
            "status", "is_active", "joining_date", "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_full_name(self, obj):
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip()


# ===============================================================
# ✅ EMPLOYEE CREATE / UPDATE SERIALIZER (Business Logic Aligned)
# ===============================================================
class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)

    department_code = serializers.CharField(write_only=True, required=False)
    manager = serializers.CharField(write_only=True, required=False, allow_null=True)
    emp_id = serializers.ReadOnlyField(source="user.emp_id")

    class Meta:
        model = Employee
        fields = [
            "id", "email", "emp_id", "first_name", "last_name", "role",
            "contact_number", "department_code", "manager", "designation",
            "status", "is_active", "joining_date"
        ]

    # =====================================================
    # VALIDATIONS
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
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Contact number must start with +91 and be a valid 10-digit Indian number.")
        qs = Employee.objects.filter(contact_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This contact number is already assigned to another employee.")
        return value

    # =====================================================
    # CREATE
    # =====================================================
    def create(self, validated_data):
        department_code = validated_data.pop("department_code", None)
        manager_emp_id = validated_data.pop("manager", None)

        # --- Department lookup ---
        department = None
        if department_code:
            try:
                department = Department.objects.get(code__iexact=department_code)
            except Department.DoesNotExist:
                raise serializers.ValidationError({
                    "department_code": f"Department with code '{department_code}' not found."
                })
            if not department.is_active:
                raise serializers.ValidationError({
                    "department_code": f"Cannot assign employee to inactive department '{department_code}'."
                })

        # --- Manager lookup ---
        manager = None
        if manager_emp_id:
            try:
                manager = Employee.objects.get(user__emp_id__iexact=manager_emp_id)
            except Employee.DoesNotExist:
                raise serializers.ValidationError({
                    "manager": f"Manager with emp_id '{manager_emp_id}' not found."
                })
            if manager.user.role != "Manager":
                raise serializers.ValidationError({
                    "manager": f"Assigned manager '{manager_emp_id}' is not a Manager role."
                })

        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        role = validated_data.pop("role")

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})

        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )

        employee = Employee.objects.create(
            user=user,
            department=department,
            manager=manager,
            **validated_data,
        )
        return employee

    # =====================================================
    # UPDATE
    # =====================================================
    def update(self, instance, validated_data):
        department_code = validated_data.pop("department_code", None)
        if department_code:
            try:
                department = Department.objects.get(code__iexact=department_code)
            except Department.DoesNotExist:
                raise serializers.ValidationError({
                    "department_code": f"Department with code '{department_code}' not found."
                })
            if not department.is_active:
                raise serializers.ValidationError({
                    "department_code": f"Cannot assign employee to inactive department '{department_code}'."
                })
            instance.department = department

        manager_emp_id = validated_data.pop("manager", None)
        if manager_emp_id:
            try:
                manager = Employee.objects.get(user__emp_id__iexact=manager_emp_id)
            except Employee.DoesNotExist:
                raise serializers.ValidationError({
                    "manager": f"Manager with emp_id '{manager_emp_id}' not found."
                })
            if manager.user.role != "Manager":
                raise serializers.ValidationError({
                    "manager": f"Assigned manager '{manager_emp_id}' is not a Manager role."
                })
            instance.manager = manager

        user = instance.user
        for field in ["email", "first_name", "last_name", "role"]:
            if field in validated_data:
                setattr(user, field, validated_data.pop(field))
        user.save()

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        return instance
