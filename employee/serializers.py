# ===============================================
# employee/serializers.py
# ===============================================
# Serializers for Department and Employee modules
# Integrated with the custom User model (username-based login)
# ===============================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Department, Employee

User = get_user_model()


# ===============================================================
# ✅ 1. DEPARTMENT SERIALIZER
# ===============================================================
class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Department CRUD.
    Enforces unique (case-insensitive) names and prevents
    deactivation when active employees exist.
    """

    employee_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at", "employee_count"]

    def get_employee_count(self, obj):
        """Returns the count of employees assigned to this department."""
        return obj.employees.count()

    def validate_name(self, value):
        """Case-insensitive uniqueness check."""
        qs = Department.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A department with this name already exists."
            )
        return value

    def validate_is_active(self, value):
        """Prevent deactivation if active employees exist."""
        if self.instance and not value:
            if Employee.objects.filter(
                department=self.instance, status="Active"
            ).exists():
                raise serializers.ValidationError(
                    "Cannot deactivate a department with active employees."
                )
        return value


# ===============================================================
# ✅ 2. USER SUMMARY SERIALIZER (READ-ONLY)
# ===============================================================
class UserSummarySerializer(serializers.ModelSerializer):
    """
    Simplified, read-only user info for embedding in Employee views.
    """

    class Meta:
        model = User
        fields = [
            "id",
            "emp_id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
        ]


# ===============================================================
# ✅ 3. EMPLOYEE READ SERIALIZER
# ===============================================================
class EmployeeSerializer(serializers.ModelSerializer):
    """
    Full employee details (used for GET/list views).
    Includes nested user & department info.
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
    Admins/Managers use this to create new employees.
    Automatically creates a linked User record.
    """

    # Linked User fields
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    emp_id = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)

    # Department linkage
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
    )

    class Meta:
        model = Employee
        fields = [
            "id",
            "username",
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
    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")
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
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        emp_id = validated_data.pop("emp_id")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        phone = validated_data.pop("phone", "")
        role = validated_data.pop("role", "Employee")

        # 1️⃣ Create linked User
        user = User.objects.create_user(
            username=username,
            email=email,
            emp_id=emp_id,
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone=phone,
        )

        # 2️⃣ Create Employee
        employee = Employee.objects.create(
            user=user,
            department=department,
            **validated_data,
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
        required=False,
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
