# ===========================================================
# employee/serializers.py ✅ Final Fixed & Frontend-Aligned
# Employee Performance Tracking System (EPTS)
# ===========================================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction, models
from .models import Department, Employee
import re, csv, io

User = get_user_model()


# ===========================================================
# ✅ DEPARTMENT SERIALIZER
# ===========================================================
class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id", "code", "name", "description", "is_active",
            "employee_count", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "employee_count"]

    def get_employee_count(self, obj):
        """Return total active employees in this department."""
        return obj.employees.filter(is_active=True).count()

    def validate_name(self, value):
        qs = Department.objects.filter(name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department with this name already exists.")
        return value.strip().title()

    def validate_code(self, value):
        if not value:
            return value
        qs = Department.objects.filter(code__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department code already exists.")
        return value.strip().upper()

    def validate_is_active(self, value):
        """Prevent deactivation if department has active employees."""
        if self.instance and not value:
            if Employee.objects.filter(department=self.instance, status="Active").exists():
                raise serializers.ValidationError("Cannot deactivate a department with active employees.")
        return value


# ===========================================================
# ✅ USER SUMMARY SERIALIZER
# ===========================================================
class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip()


# ===========================================================
# ✅ EMPLOYEE SERIALIZER (Detailed)
# ===========================================================
class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)

    emp_id = serializers.ReadOnlyField(source="user.emp_id")
    first_name = serializers.ReadOnlyField(source="user.first_name")
    last_name = serializers.ReadOnlyField(source="user.last_name")
    full_name = serializers.SerializerMethodField(read_only=True)
    email = serializers.ReadOnlyField(source="user.email")
    role = serializers.ReadOnlyField(source="user.role")
    department_name = serializers.ReadOnlyField(source="department.name")
    department_code = serializers.ReadOnlyField(source="department.code")
    manager_name = serializers.ReadOnlyField()
    reporting_to = serializers.ReadOnlyField(source="reporting_to_name")
    team_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "user", "emp_id", "first_name", "last_name", "full_name", "email",
            "phone", "department", "department_name", "department_code",
            "role", "manager", "manager_name", "reporting_to", "designation",
            "status", "is_active", "joining_date", "team_size",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_full_name(self, obj):
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip()


# ===========================================================
# ✅ EMPLOYEE CREATE / UPDATE SERIALIZER (Fixed)
# ===========================================================
class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)
    department_code = serializers.CharField(write_only=True, required=False)
    manager = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emp_id = serializers.ReadOnlyField(source="user.emp_id")

    class Meta:
        model = Employee
        fields = [
            "id", "email", "emp_id", "first_name", "last_name", "role",
            "phone", "department_code", "manager", "designation",
            "status", "is_active", "joining_date",
        ]

    def validate_phone(self, value):
        """Validate Indian +91 format and uniqueness."""
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Phone must start with +91 and be a valid 10-digit number.")
        qs = Employee.objects.filter(phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This phone number is already used by another employee.")
        return value

    def validate_role(self, value):
        if value not in dict(User.ROLE_CHOICES):
            raise serializers.ValidationError("Invalid role. Choose Admin, Manager, or Employee.")
        return value

    # =======================================================
    # ✅ CREATE
    # =======================================================
    @transaction.atomic
    def create(self, validated_data):
        department_code = validated_data.pop("department_code", None)
        manager_emp_id = validated_data.pop("manager", None)
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        role = validated_data.pop("role")

        # --- Department validation ---
        department = None
        if role == "Employee" and not department_code:
            raise serializers.ValidationError({"department_code": "Department is required for Employee role."})
        if department_code:
            department = Department.objects.filter(
                models.Q(id__iexact=department_code)
                | models.Q(code__iexact=department_code)
                | models.Q(name__iexact=department_code)
            ).first()
            if not department:
                raise serializers.ValidationError({"department_code": f"Department '{department_code}' not found."})
            if not department.is_active:
                raise serializers.ValidationError({"department_code": f"Cannot assign to inactive department '{department_code}'."})

        # --- Manager validation ---
        manager = None
        if manager_emp_id:
            manager = Employee.objects.filter(user__emp_id__iexact=manager_emp_id).first()
            if not manager:
                raise serializers.ValidationError({"manager": f"Manager '{manager_emp_id}' not found."})
            if manager.user.role not in ["Manager", "Admin"]:
                raise serializers.ValidationError({"manager": f"Assigned manager must be Manager/Admin."})

        # --- Unique Email Check ---
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "User with this email already exists."})

        # --- Create user linked with department ---
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            department=department,
        )

        # --- Create employee record ---
        employee = Employee.objects.create(
            user=user,
            department=department,
            manager=manager,
            **validated_data,
        )
        return employee

    # =======================================================
    # ✅ UPDATE (Admin / Department / Manager Edits)
    # =======================================================
    @transaction.atomic
    def update(self, instance, validated_data):
        department_value = validated_data.pop("department_code", None)
        manager_value = validated_data.pop("manager", None)
        role = validated_data.get("role")

        # --- Department update (id/code/name) ---
        if department_value:
            department = Department.objects.filter(
                models.Q(id__iexact=department_value)
                | models.Q(code__iexact=department_value)
                | models.Q(name__iexact=department_value)
            ).first()
            if not department:
                raise serializers.ValidationError({
                    "department_code": f"Department '{department_value}' not found."
                })
            if not department.is_active:
                raise serializers.ValidationError({
                    "department_code": f"Cannot assign to inactive department '{department_value}'."})
            instance.department = department
            instance.user.department = department

        # --- Manager update (emp_id or username) ---
        if manager_value:
            manager = (
                Employee.objects.filter(user__emp_id__iexact=manager_value).first()
                or Employee.objects.filter(user__username__iexact=manager_value).first()
            )
            if not manager:
                raise serializers.ValidationError({
                    "manager": f"Manager '{manager_value}' not found."
                })
            if manager.user.role not in ["Manager", "Admin"]:
                raise serializers.ValidationError({
                    "manager": f"Assigned manager must be Manager/Admin."
                })
            instance.manager = manager

        # --- Role update (Admin, Manager, Employee) ---
        if role:
            if role not in dict(User.ROLE_CHOICES):
                raise serializers.ValidationError({"role": "Invalid role."})
            instance.user.role = role

        # --- Sync User fields ---
        user = instance.user
        for field in ["email", "first_name", "last_name", "role"]:
            if field in validated_data:
                setattr(user, field, validated_data.pop(field))
        user.save()

        # --- Update Employee fields ---
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        return instance


# ===========================================================
# ✅ EMPLOYEE DASHBOARD SERIALIZER
# ===========================================================
class EmployeeDashboardSerializer(serializers.ModelSerializer):
    emp_id = serializers.ReadOnlyField(source="user.emp_id")
    full_name = serializers.SerializerMethodField()
    email = serializers.ReadOnlyField(source="user.email")
    department_name = serializers.ReadOnlyField(source="department.name")
    manager_name = serializers.ReadOnlyField()
    role = serializers.ReadOnlyField(source="user.role")
    status = serializers.CharField()
    team_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "emp_id", "full_name", "email",
            "department_name", "manager_name", "role",
            "status", "joining_date", "team_size",
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip() or obj.user.username


# ===========================================================
# ✅ EMPLOYEE BULK CSV UPLOAD SERIALIZER
# ===========================================================
class EmployeeCSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith(".csv"):
            raise serializers.ValidationError("Only CSV files are allowed.")
        return value

    def create(self, validated_data):
        file = validated_data["file"]
        decoded_file = file.read().decode("utf-8")
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        required_columns = ["Emp Id", "First Name", "Last Name", "Email", "Dept Code", "Role", "Joining Date"]
        if not all(col in reader.fieldnames for col in required_columns):
            raise serializers.ValidationError({"error": f"CSV must contain headers: {', '.join(required_columns)}"})

        success_count, errors = 0, []

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                emp_id = row.get("Emp Id", "").strip()
                first_name = row.get("First Name", "").strip()
                last_name = row.get("Last Name", "").strip()
                email = row.get("Email", "").strip()
                dept_code = row.get("Dept Code", "").strip()
                role = row.get("Role", "").strip().capitalize()
                joining_date = row.get("Joining Date", "").strip()

                if not (emp_id and first_name and email and dept_code and role):
                    errors.append(f"Row {i}: Missing mandatory fields.")
                    continue

                if Employee.objects.filter(user__emp_id__iexact=emp_id).exists():
                    errors.append(f"Row {i}: Employee ID '{emp_id}' already exists.")
                    continue

                if User.objects.filter(email__iexact=email).exists():
                    errors.append(f"Row {i}: Email '{email}' already exists.")
                    continue

                department = Department.objects.filter(code__iexact=dept_code).first()
                if not department:
                    errors.append(f"Row {i}: Department code '{dept_code}' not found.")
                    continue

                if role not in ["Admin", "Manager", "Employee"]:
                    errors.append(f"Row {i}: Invalid role '{role}'.")
                    continue

                try:
                    user = User.objects.create_user(
                        email=email,
                        first_name=first_name,
                        last_name=last_name,
                        role=role,
                        department=department,
                    )
                    user.emp_id = emp_id
                    user.set_password("Default@123")
                    user.save()

                    Employee.objects.create(
                        user=user,
                        department=department,
                        joining_date=joining_date or None,
                        status="Active",
                        is_active=True,
                    )
                    success_count += 1

                except Exception as e:
                    errors.append(f"Row {i}: {str(e)}")

        return {"success_count": success_count, "errors": errors}
