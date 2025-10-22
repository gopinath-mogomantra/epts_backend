# ===============================================
# employee/serializers.py
# ===============================================


from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Department, Employee
import re

User = get_user_model()


# ===============================================================
# ✅ 1. DEPARTMENT SERIALIZER
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
# ✅ 2. USER SUMMARY SERIALIZER (READ-ONLY)
# ===============================================================
class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "emp_id", "username", "first_name", "last_name", "email", "role"]


# ===============================================================
# ✅ 3. EMPLOYEE SERIALIZER (List / Detail)
# ===============================================================
class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    manager_name = serializers.ReadOnlyField()

    emp_id = serializers.ReadOnlyField(source="user.emp_id")
    first_name = serializers.ReadOnlyField(source="user.first_name")
    last_name = serializers.ReadOnlyField(source="user.last_name")
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


# ===============================================================
# ✅ 4. EMPLOYEE CREATE / UPDATE SERIALIZER (Business Logic Enforced)
# ===============================================================
class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Used for POST and PUT/PATCH operations.
    Automatically creates / updates the linked User record.
    Applies strict validation rules for business logic.
    """

    # Linked User fields
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    emp_id = serializers.CharField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    # Department relation
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=False,
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
            "role",
            "password",
            "contact_number",
            "department_id",
            "manager",
            "designation",
            "status",
            "joining_date",
        ]

    # =====================================================
    # ✅ FIELD-LEVEL VALIDATION
    # =====================================================
    def validate_first_name(self, value):
        if not re.match(r"^[A-Za-z ]+$", value):
            raise serializers.ValidationError("First name must contain only letters and spaces.")
        return value.strip().title()

    def validate_last_name(self, value):
        if not re.match(r"^[A-Za-z ]+$", value):
            raise serializers.ValidationError("Last name must contain only letters and spaces.")
        return value.strip().title()

    def validate_designation(self, value):
        if not re.match(r"^[A-Za-z ]+$", value):
            raise serializers.ValidationError("Designation must contain only alphabets (e.g., 'Lead Developer').")
        return value.strip().title()

    def validate_contact_number(self, value):
        import re
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Contact number must start with +91 and be a valid 10-digit Indian mobile number."
            )
        return value


    def validate_username(self, value):
        qs = User.objects.filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user.id)
        if qs.exists():
            raise serializers.ValidationError("Username already exists.")
        return value.strip()

    def validate_email(self, value):
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user.id)
        if qs.exists():
            raise serializers.ValidationError("Email already exists.")
        return value.lower()

    def validate_emp_id(self, value):
        qs = User.objects.filter(emp_id__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user.id)
        if qs.exists():
            raise serializers.ValidationError("Employee ID already exists.")
        return value.upper()

    def validate_manager(self, value):
        if value and self.instance and value.id == self.instance.id:
            raise serializers.ValidationError("An employee cannot be their own manager.")
        if value and value.user.role != "Manager":
            raise serializers.ValidationError("Assigned manager must have a Manager role.")
        return value

    def validate_department(self, value):
        if value and not value.is_active:
            raise serializers.ValidationError("Cannot assign employees to an inactive department.")
        return value

    def validate_status(self, value):
        valid_statuses = ["Active", "On Leave", "Resigned"]
        if value not in valid_statuses:
            raise serializers.ValidationError("Invalid employee status.")
        return value

    # =====================================================
    # ✅ OBJECT-LEVEL VALIDATION (Cross-field Business Rules)
    # =====================================================
    def validate(self, data):
        role = data.get("role")
        designation = data.get("designation")

        if role == "Manager" and designation and "Manager" not in designation:
            raise serializers.ValidationError({
                "designation": "Designation must include 'Manager' for Manager role."
            })
        if role == "Employee" and designation and "Manager" in designation:
            raise serializers.ValidationError({
                "designation": "Employee role cannot have 'Manager' in designation."
            })

        return data

    # =====================================================
    # ✅ CREATE METHOD
    # =====================================================
    def create(self, validated_data):
        department = validated_data.pop("department", None)
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        emp_id = validated_data.pop("emp_id")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        role = validated_data.pop("role")
        password = validated_data.pop("password", None) or "admin123"

        user = User.objects.create_user(
            username=username,
            email=email,
            emp_id=emp_id,
            first_name=first_name,
            last_name=last_name,
            role=role,
            password=password,
        )

        employee = Employee.objects.create(user=user, department=department, **validated_data)
        return employee

    # =====================================================
    # ✅ UPDATE METHOD — Strict Business Logic Enforcement
    # =====================================================
    def update(self, instance, validated_data):
        department = validated_data.pop("department", None)
        if department:
            instance.department = department

        # Update linked User fields
        user = instance.user
        user_fields = ["username", "email", "emp_id", "first_name", "last_name", "role"]
        for field in user_fields:
            if field in validated_data:
                setattr(user, field, validated_data.pop(field))
        user.save()

        # Update only allowed employee fields
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
