# ===========================================================
# employee/serializers.py ✅ Final Cleaned & Feature-Enhanced
# Employee Performance Tracking System (EPTS)
# ===========================================================

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction, models
from .models import Department, Employee
import re, csv, io
from datetime import datetime, date

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
        return obj.employees.filter(status="Active").count()

    def validate_name(self, value):
        value = value.strip().title()
        qs = Department.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department with this name already exists.")
        return value

    def validate_code(self, value):
        if not value:
            return value
        value = value.strip().upper()
        qs = Department.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department code already exists.")
        return value

    def validate_is_active(self, value):
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
# ✅ EMPLOYEE SERIALIZER (Detailed Read-Only)
# ===========================================================
class EmployeeSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)

    emp_id = serializers.ReadOnlyField(source="user.emp_id")
    full_name = serializers.SerializerMethodField(read_only=True)
    email = serializers.ReadOnlyField(source="user.email")
    role = serializers.ReadOnlyField(source="user.role")
    department_name = serializers.ReadOnlyField(source="department.name")
    department_code = serializers.ReadOnlyField(source="department.code")
    manager_name = serializers.SerializerMethodField(read_only=True)
    team_size = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "user", "emp_id", "full_name", "email", "contact_number",
            "department", "department_name", "department_code",
            "role", "manager", "manager_name", "designation",
            "status", "joining_date", "team_size",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_full_name(self, obj):
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip()

    def get_manager_name(self, obj):
        if obj.manager and hasattr(obj.manager, "user"):
            return f"{obj.manager.user.first_name} {obj.manager.user.last_name}".strip()
        return "Not Assigned"

    def get_team_size(self, obj):
        return Employee.objects.filter(manager=obj).count()


# ===========================================================
# ✅ EMPLOYEE CREATE / UPDATE SERIALIZER
# ===========================================================
class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)
    department_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    department_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    manager = serializers.CharField(write_only=True, required=False, allow_blank=True)
    emp_id = serializers.ReadOnlyField(source="user.emp_id")

    class Meta:
        model = Employee
        fields = [
            "id", "email", "emp_id", "first_name", "last_name", "role",
            "contact_number", "department_code", "department_name",
            "manager", "designation", "status", "joining_date",
        ]

    # =======================================================
    # ✅ VALIDATIONS
    # =======================================================
    def validate_contact_number(self, value):
        if not value:
            return value
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError("Contact number must start with +91 and be valid.")
        qs = Employee.objects.filter(contact_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This contact number is already used.")
        return value

    def validate_joining_date(self, value):
        """Prevent joining date from being a future date."""
        if value and value > date.today():
            raise serializers.ValidationError("Joining date cannot be in the future.")
        return value

    # =======================================================
    # ✅ CREATE
    # =======================================================
    @transaction.atomic
    def create(self, validated_data):
        dept_code = validated_data.pop("department_code", None)
        dept_name = validated_data.pop("department_name", None)
        manager_emp_id = validated_data.pop("manager", None)
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        role = validated_data.pop("role")

        # --- Department Validation ---
        if not dept_code and not dept_name:
            raise serializers.ValidationError({
                "department": "Either 'department_code' or 'department_name' must be provided."
            })
        if dept_code and dept_name:
            raise serializers.ValidationError({
                "department": "Provide only one of 'department_code' or 'department_name', not both."
            })

        dept_identifier = dept_code or dept_name
        department = Department.objects.filter(
            models.Q(id__iexact=dept_identifier)
            | models.Q(code__iexact=dept_identifier)
            | models.Q(name__iexact=dept_identifier)
        ).first()
        if not department:
            raise serializers.ValidationError({"department": f"Department '{dept_identifier}' not found."})
        if not department.is_active:
            raise serializers.ValidationError({"department": f"Department '{department.name}' is inactive."})

        # --- Manager Validation ---
        manager = None
        if manager_emp_id:
            manager = Employee.objects.filter(user__emp_id__iexact=manager_emp_id).first()
            if not manager:
                raise serializers.ValidationError({"manager": f"Manager '{manager_emp_id}' not found."})
            if manager.user.role not in ["Manager", "Admin"]:
                raise serializers.ValidationError({"manager": "Assigned manager must be Manager/Admin."})

        # --- Email Uniqueness ---
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError({"email": "User with this email already exists."})

        # --- Create User & Employee ---
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            department=department,
        )
        employee = Employee.objects.create(
            user=user,
            department=department,
            manager=manager,
            **validated_data,
        )
        return employee

    # =======================================================
    # ✅ UPDATE
    # =======================================================
    @transaction.atomic
    def update(self, instance, validated_data):
        dept_code = validated_data.pop("department_code", None)
        dept_name = validated_data.pop("department_name", None)
        manager_value = validated_data.pop("manager", None)
        role = validated_data.get("role")

        # --- Department Update ---
        if dept_code or dept_name:
            if dept_code and dept_name:
                raise serializers.ValidationError({
                    "department": "Provide only one of 'department_code' or 'department_name', not both."
                })
            dept_identifier = dept_code or dept_name
            department = Department.objects.filter(
                models.Q(id__iexact=dept_identifier)
                | models.Q(code__iexact=dept_identifier)
                | models.Q(name__iexact=dept_identifier)
            ).first()
            if not department:
                raise serializers.ValidationError({"department": f"Department '{dept_identifier}' not found."})
            instance.department = department
            instance.user.department = department
            instance.user.save(update_fields=["department"])

        # --- Manager Update ---
        if manager_value:
            manager = Employee.objects.filter(user__emp_id__iexact=manager_value).first()
            if not manager:
                raise serializers.ValidationError({"manager": f"Manager '{manager_value}' not found."})
            if manager.user.role not in ["Manager", "Admin"]:
                raise serializers.ValidationError({"manager": "Assigned manager must be Manager/Admin."})
            instance.manager = manager
            instance.save(update_fields=["manager"])

        # --- Role Update ---
        if role:
            instance.user.role = role
            instance.user.save(update_fields=["role"])

        # --- Sync User Fields ---
        user = instance.user
        for field in ["email", "first_name", "last_name"]:
            if field in validated_data:
                setattr(user, field, validated_data.pop(field))
        user.save()

        # --- Update Employee Fields ---
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
    manager_name = serializers.SerializerMethodField(read_only=True)
    role = serializers.ReadOnlyField(source="user.role")
    team_size = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id", "emp_id", "full_name", "email",
            "department_name", "manager_name", "role",
            "status", "joining_date", "team_size",
        ]

    def get_full_name(self, obj):
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip()

    def get_manager_name(self, obj):
        if obj.manager and hasattr(obj.manager, "user"):
            return f"{obj.manager.user.first_name} {obj.manager.user.last_name}".strip()
        return "-"

    def get_team_size(self, obj):
        return Employee.objects.filter(manager=obj).count()


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

        required_cols = ["Emp Id", "First Name", "Last Name", "Email", "Dept Code", "Role", "Joining Date"]
        if not all(col in reader.fieldnames for col in required_cols):
            raise serializers.ValidationError({"error": f"CSV must contain: {', '.join(required_cols)}"})

        success_count, errors = 0, []

        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                emp_id = row.get("Emp Id", "").strip()
                email = row.get("Email", "").strip().lower()
                dept_code = row.get("Dept Code", "").strip()
                first_name = row.get("First Name", "").strip()
                last_name = row.get("Last Name", "").strip()
                role = row.get("Role", "").strip().capitalize()
                joining_date = row.get("Joining Date", "").strip()

                if not (emp_id and email and dept_code and role):
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
                    errors.append(f"Row {i}: Department '{dept_code}' not found.")
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

                    join_date = None
                    if joining_date:
                        try:
                            join_date = datetime.strptime(joining_date, "%Y-%m-%d").date()
                        except ValueError:
                            pass

                    Employee.objects.create(
                        user=user,
                        department=department,
                        joining_date=join_date or None,
                        status="Active",
                    )
                    success_count += 1

                except Exception as e:
                    errors.append(f"Row {i}: {str(e)}")

        return {"success_count": success_count, "errors": errors}
