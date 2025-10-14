# ===============================================
# employee/serializers.py
# ===============================================
# Serializers for Department and Employee models
# Linked to the custom User model
# ===============================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Department, Employee

User = get_user_model()


# ===============================================================
# ✅ 1. DEPARTMENT SERIALIZER + VALIDATION
# ===============================================================
class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and managing departments.
    Ensures unique name and prevents deactivation if employees exist.
    """

    class Meta:
        model = Department
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def validate_name(self, value):
        """
        Case-insensitive unique check for department names.
        """
        qs = Department.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A department with this name already exists.")
        return value

    def validate_is_active(self, value):
        """
        Prevent deactivation if active employees exist.
        """
        if self.instance and not value:
            has_employees = Employee.objects.filter(department=self.instance, status="Active").exists()
            if has_employees:
                raise serializers.ValidationError("Cannot deactivate department with active employees.")
        return value


# ===============================================================
# ✅ 2. USER SUMMARY SERIALIZER
# ===============================================================
class UserSummarySerializer(serializers.ModelSerializer):
    """
    Read-only serializer for linked user details.
    """

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "email", "role"]


# ===============================================================
# ✅ 3. EMPLOYEE READ SERIALIZER
# ===============================================================
class EmployeeSerializer(serializers.ModelSerializer):
    """
    Full employee details (used for GET requests).
    """
    user = UserSummarySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    manager_name = serializers.ReadOnlyField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "user",
            "department",
            "manager",
            "manager_name",
            "designation",
            "status",
            "date_joined",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


# ===============================================================
# ✅ 4. EMPLOYEE CREATION SERIALIZER (WRITE)
# ===============================================================
class EmployeeCreateSerializer(serializers.ModelSerializer):
    """
    Used by Admins/Managers to create new employees.
    Automatically creates linked User entry.
    """

    # Linked User fields
    email = serializers.EmailField(write_only=True)
    emp_id = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.ChoiceField(
        choices=User.ROLE_CHOICES,
        write_only=True,
        help_text="Select role: Admin / Manager / Employee"
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True
    )

    class Meta:
        model = Employee
        fields = [
            "id",
            "email",
            "emp_id",
            "first_name",
            "last_name",
            "phone",
            "role",
            "department_id",
            "manager",
            "designation",
            "status",
        ]

    # -------------------------------
    # 🔹 VALIDATION SECTION
    # -------------------------------
    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_emp_id(self, value):
        if User.objects.filter(emp_id__iexact=value).exists():
            raise serializers.ValidationError("Employee ID already exists.")
        return value

    def validate_manager(self, value):
        if value and self.instance and value.id == self.instance.id:
            raise serializers.ValidationError("An employee cannot be their own manager.")
        return value

    def validate_department(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError("Cannot assign employees to an inactive department.")
        return value

    def validate(self, attrs):
        if "status" in attrs and attrs["status"] not in ["Active", "On Leave", "Resigned"]:
            raise serializers.ValidationError({"status": "Invalid employee status."})
        return attrs

    # -------------------------------
    # 🔹 CREATE LOGIC
    # -------------------------------
    def create(self, validated_data):
        department = validated_data.pop("department", None)
        email = validated_data.pop("email")
        emp_id = validated_data.pop("emp_id")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        phone = validated_data.pop("phone", "")
        role = validated_data.pop("role", "Employee")

        # 1️⃣ Create linked User
        user = User.objects.create_user(
            email=email,
            emp_id=emp_id,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone=phone
        )

        # 2️⃣ Create Employee record
        employee = Employee.objects.create(
            user=user,
            department=department,
            **validated_data
        )

        return employee


# ===============================================================
# ✅ 5. EMPLOYEE UPDATE SERIALIZER
# ===============================================================
class EmployeeUpdateSerializer(serializers.ModelSerializer):
    """
    Used for PUT/PATCH updates (Admin/Manager use).
    """
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        required=False
    )

    class Meta:
        model = Employee
        fields = ["department_id", "manager", "designation", "status"]

    def validate_manager(self, value):
        if value and self.instance and value.id == self.instance.id:
            raise serializers.ValidationError("An employee cannot be their own manager.")
        return value

    def validate_department(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError("Cannot assign to an inactive department.")
        return value

    def validate_status(self, value):
        if value not in ["Active", "On Leave", "Resigned"]:
            raise serializers.ValidationError("Invalid status value.")
        return value
