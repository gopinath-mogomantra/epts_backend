from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Department, Employee
from users.models import Role

User = get_user_model()


# ===============================================================
# ✅ 1. DEPARTMENT SERIALIZER + VALIDATION
# ===============================================================
class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and managing departments.
    Ensures name uniqueness and prevents deactivation if employees exist.
    """
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ["created_at", "updated_at"]
        ref_name = "EmployeeDepartment"

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
        Prevent deactivating a department that still has active employees.
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
    role = serializers.StringRelatedField()

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "email", "role"]


# ===============================================================
# ✅ 3. EMPLOYEE SERIALIZER (READ)
# ===============================================================
class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    manager_name = serializers.ReadOnlyField()

    class Meta:
        model = Employee
        fields = [
            "id", "user", "department", "manager", "manager_name",
            "role_title", "joining_date", "status", "created_at", "updated_at"
        ]
        read_only_fields = ["created_at", "updated_at"]


# ===============================================================
# ✅ 4. EMPLOYEE CREATION SERIALIZER (WRITE)
# ===============================================================
class EmployeeCreateSerializer(serializers.ModelSerializer):
    """
    Handles employee creation (Admin/Manager only).
    Includes validation for unique email, emp_id, and valid relationships.
    """

    # Linked CustomUser fields
    email = serializers.EmailField(write_only=True)
    emp_id = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        source="role",
        write_only=True
    )
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True
    )

    class Meta:
        model = Employee
        fields = [
            "id", "email", "emp_id", "first_name", "last_name",
            "phone", "role_id", "department_id", "manager",
            "role_title", "joining_date", "status"
        ]

    # ==========================================================
    # 🔹 VALIDATION SECTION
    # ==========================================================

    def validate_email(self, value):
        """
        Ensure email is unique across all users.
        """
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_emp_id(self, value):
        """
        Ensure employee ID is unique across all users.
        """
        if User.objects.filter(emp_id__iexact=value).exists():
            raise serializers.ValidationError("Employee ID already exists.")
        return value

    def validate_manager(self, value):
        """
        Ensure employee is not assigned as their own manager.
        """
        if value and self.instance and value.id == self.instance.id:
            raise serializers.ValidationError("An employee cannot be their own manager.")
        return value

    def validate_department(self, value):
        """
        Ensure department is active before assigning employees.
        """
        if value and not value.is_active:
            raise serializers.ValidationError("Cannot assign employees to an inactive department.")
        return value

    def validate_joining_date(self, value):
        """
        Prevent joining date in the future.
        """
        if value > timezone.now().date():
            raise serializers.ValidationError("Joining date cannot be in the future.")
        return value

    # ==========================================================
    # 🔹 CREATE LOGIC
    # ==========================================================
    def create(self, validated_data):
        role = validated_data.pop("role", None)
        department = validated_data.pop("department", None)
        email = validated_data.pop("email")
        emp_id = validated_data.pop("emp_id")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        phone = validated_data.pop("phone", "")

        # 1️⃣ Create CustomUser
        user = User.objects.create_user(
            username=email,
            email=email,
            emp_id=emp_id,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
        user.phone = phone
        user.save()

        # 2️⃣ Create Employee record
        employee = Employee.objects.create(
            user=user,
            department=department,
            **validated_data
        )

        return employee


# ===============================================================
# ✅ 5. EMPLOYEE UPDATE VALIDATION (optional)
# ===============================================================
class EmployeeUpdateSerializer(serializers.ModelSerializer):
    """
    Used for PUT/PATCH update operations.
    Ensures department and manager validity.
    """
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        required=False
    )

    class Meta:
        model = Employee
        fields = [
            "department_id", "manager", "role_title", "status"
        ]

    def validate_manager(self, value):
        """
        Prevent self-assignment as manager.
        """
        if value and self.instance and value.id == self.instance.id:
            raise serializers.ValidationError("An employee cannot be their own manager.")
        return value

    def validate_department(self, value):
        """
        Ensure department is active.
        """
        if value and not value.is_active:
            raise serializers.ValidationError("Cannot assign to an inactive department.")
        return value

    def validate_status(self, value):
        """
        Ensure valid status transition.
        """
        allowed_status = ["Active", "On Leave", "Resigned"]
        if value not in allowed_status:
            raise serializers.ValidationError("Invalid status value.")
        return value
