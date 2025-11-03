# ===========================================================
# employee/serializers.py (Enhanced Version — 01-Nov-2025)
# ===========================================================
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Department, Employee
import re
import csv
import io
import os
import secrets
from datetime import datetime, date

User = get_user_model()


# ===========================================================
# UTILITY FUNCTIONS
# ===========================================================
def generate_secure_password(length=12):
    """Generate a cryptographically secure random password."""
    return secrets.token_urlsafe(length)


def send_welcome_email(user, temp_password):
    """Send welcome email with temporary password."""
    try:
        subject = "Welcome to Employee Management System"
        message = f"""
        Hello {user.first_name} {user.last_name},

        Welcome to our organization!

        Your account has been created with the following credentials:
        Email: {user.email}
        Employee ID: {user.emp_id}
        Temporary Password: {temp_password}

        Please log in and change your password immediately.

        Best regards,
        HR Team
        """
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    except Exception as e:
        # Log error but don't break the flow
        print(f"Failed to send welcome email to {user.email}: {str(e)}")


def validate_image_file(value):
    """Common image validation for profile pictures."""
    if value:
        ext = os.path.splitext(value.name)[1].lower()
        valid_extensions = [".jpg", ".jpeg", ".png"]
        max_size = 2 * 1024 * 1024  # 2MB

        if ext not in valid_extensions:
            raise serializers.ValidationError(
                f"Only {', '.join(valid_extensions)} images are allowed."
            )
        if value.size > max_size:
            raise serializers.ValidationError(
                f"Profile picture size must not exceed {max_size / (1024 * 1024):.0f}MB."
            )
    return value


# ===========================================================
# DEPARTMENT SERIALIZER
# ===========================================================
class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_active",
            "employee_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "employee_count"]

    def get_employee_count(self, obj):
        """Count active employees in department."""
        # Use prefetch_related in viewset for optimization
        if hasattr(obj, "_employee_count"):
            return obj._employee_count
        return obj.employees.filter(status="Active").count()

    def validate_name(self, value):
        """Ensure department name is unique (case-insensitive)."""
        value = value.strip().title()
        qs = Department.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Department with this name already exists."
            )
        return value

    def validate_code(self, value):
        """Ensure department code is unique and properly formatted."""
        if not value:
            return value

        value = value.strip().upper()

        # Validate code format
        if not re.match(r"^[A-Z0-9_-]{2,10}$", value):
            raise serializers.ValidationError(
                "Department code must be 2-10 characters (letters, numbers, underscores, hyphens only)."
            )

        qs = Department.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Department code already exists.")
        return value

    def validate_is_active(self, value):
        """Prevent deactivating departments with active employees."""
        if self.instance and not value:
            active_count = Employee.objects.filter(
                department=self.instance, status="Active"
            ).count()
            if active_count > 0:
                raise serializers.ValidationError(
                    f"Cannot deactivate department with {active_count} active employee(s). "
                    "Please reassign or deactivate employees first."
                )
        return value


# ===========================================================
# USER SUMMARY SERIALIZER
# ===========================================================
class UserSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "emp_id", "first_name", "last_name", "full_name", "email", "role"]

    def get_full_name(self, obj):
        """Return formatted full name."""
        return f"{obj.first_name or ''} {obj.last_name or ''}".strip() or "N/A"


# ===========================================================
# EMPLOYEE SERIALIZER (Read-Only)
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
            "id",
            "user",
            "emp_id",
            "full_name",
            "email",
            "contact_number",
            "department",
            "department_name",
            "department_code",
            "role",
            "manager",
            "manager_name",
            "designation",
            "status",
            "joining_date",
            "team_size",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_full_name(self, obj):
        """Return formatted full name."""
        return f"{obj.user.first_name or ''} {obj.user.last_name or ''}".strip() or "N/A"

    def get_manager_name(self, obj):
        """Return manager's full name."""
        if obj.manager and hasattr(obj.manager, "user"):
            return (
                f"{obj.manager.user.first_name} {obj.manager.user.last_name}".strip()
                or "N/A"
            )
        return "Not Assigned"

    def get_team_size(self, obj):
        """Count direct reports."""
        if hasattr(obj, "_team_size"):
            return obj._team_size
        return Employee.objects.filter(manager=obj, status="Active").count()


# ===========================================================
# EMPLOYEE CREATE / UPDATE SERIALIZER
# ===========================================================
class EmployeeCreateUpdateSerializer(serializers.ModelSerializer):
    # User-related fields
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True, max_length=150)
    last_name = serializers.CharField(write_only=True, max_length=150)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, write_only=True)

    # Department fields (provide one)
    department_code = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    department_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    # Manager field
    manager_emp_id = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    # Read-only output
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
            "department_code",
            "department_name",
            "manager_emp_id",
            "designation",
            "status",
            "joining_date",
        ]

    def validate_email(self, value):
        """Validate email format and uniqueness."""
        value = value.strip().lower()

        # Additional email format validation
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
            raise serializers.ValidationError("Invalid email format.")

        # Check uniqueness (skip for updates)
        if not self.instance:
            if User.objects.filter(email__iexact=value).exists():
                raise serializers.ValidationError(
                    f"User with email '{value}' already exists."
                )
        return value

    def validate_contact_number(self, value):
        """Validate Indian phone number format."""
        if not value:
            return value

        # Indian mobile number: +91 followed by 10 digits starting with 6-9
        pattern = r"^\+91[6-9]\d{9}$"
        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Contact number must be in format: +91XXXXXXXXXX (10 digits starting with 6-9)."
            )

        # Check uniqueness
        qs = Employee.objects.filter(contact_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "This contact number is already registered."
            )
        return value

    def validate_joining_date(self, value):
        """Validate joining date is not in future."""
        if value:
            if value > date.today():
                raise serializers.ValidationError(
                    "Joining date cannot be in the future."
                )
            # Reasonable lower bound (e.g., company founded date)
            if value.year < 1950:
                raise serializers.ValidationError("Please provide a valid joining date.")
        return value

    def validate(self, data):
        """Cross-field validation."""
        # Validate department input
        dept_code = data.get("department_code", "").strip()
        dept_name = data.get("department_name", "").strip()

        if dept_code and dept_name:
            raise serializers.ValidationError(
                {
                    "department": "Provide only one of 'department_code' or 'department_name', not both."
                }
            )

        if not dept_code and not dept_name:
            raise serializers.ValidationError(
                {
                    "department": "You must provide either 'department_code' or 'department_name'."
                }
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        """Create new employee with user account."""
        # Extract user and department data
        email = validated_data.pop("email").strip().lower()
        first_name = validated_data.pop("first_name").strip()
        last_name = validated_data.pop("last_name").strip()
        role = validated_data.pop("role")
        dept_code = validated_data.pop("department_code", "").strip()
        dept_name = validated_data.pop("department_name", "").strip()
        manager_emp_id = validated_data.pop("manager_emp_id", "").strip()

        # =============== Resolve Department ===============
        department = self._resolve_department(dept_code, dept_name)

        # =============== Resolve Manager ===============
        manager = self._resolve_manager(manager_emp_id)

        # =============== Create User ===============
        try:
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                role=role,
                department=department,
            )
        except Exception as e:
            raise serializers.ValidationError({"user": f"User creation failed: {str(e)}"})

        # =============== Create Employee ===============
        employee = Employee.objects.create(
            user=user,
            department=department,
            manager=manager,
            **validated_data,
        )

        return employee

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update existing employee."""
        # Extract department and manager data
        dept_code = validated_data.pop("department_code", "").strip()
        dept_name = validated_data.pop("department_name", "").strip()
        manager_emp_id = validated_data.pop("manager_emp_id", "").strip()

        # User fields (if provided)
        if "email" in validated_data:
            validated_data.pop("email")  # Cannot change email after creation
        if "first_name" in validated_data:
            instance.user.first_name = validated_data.pop("first_name").strip()
        if "last_name" in validated_data:
            instance.user.last_name = validated_data.pop("last_name").strip()
        if "role" in validated_data:
            instance.user.role = validated_data.pop("role")
        instance.user.save()

        # Update department if provided
        if dept_code or dept_name:
            department = self._resolve_department(dept_code, dept_name)
            instance.department = department
            instance.user.department = department
            instance.user.save()

        # Update manager if provided
        if manager_emp_id:
            manager = self._resolve_manager(manager_emp_id)
            instance.manager = manager

        # Update remaining fields
        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()
        return instance

    def _resolve_department(self, dept_code, dept_name):
        """Resolve and validate department."""
        if dept_code:
            # Validate code format
            if not re.match(r"^[A-Za-z0-9_-]+$", dept_code):
                raise serializers.ValidationError(
                    {
                        "department_code": "Invalid format. Department codes must not contain spaces."
                    }
                )
            department = Department.objects.filter(code__iexact=dept_code).first()
            if not department:
                raise serializers.ValidationError(
                    {"department_code": f"Department with code '{dept_code}' not found."}
                )
        elif dept_name:
            department = Department.objects.filter(name__iexact=dept_name).first()
            if not department:
                raise serializers.ValidationError(
                    {"department_name": f"Department '{dept_name}' not found."}
                )
        else:
            raise serializers.ValidationError(
                {"department": "Department code or name is required."}
            )

        # Check if department is active
        if not department.is_active:
            raise serializers.ValidationError(
                {"department": f"Department '{department.name}' is currently inactive."}
            )

        return department

    def _resolve_manager(self, manager_emp_id):
        """Resolve and validate manager."""
        if not manager_emp_id:
            return None

        manager = Employee.objects.filter(user__emp_id__iexact=manager_emp_id).first()
        if not manager:
            raise serializers.ValidationError(
                {"manager_emp_id": f"Manager with ID '{manager_emp_id}' not found."}
            )

        if manager.user.role not in ["Manager", "Admin"]:
            raise serializers.ValidationError(
                {
                    "manager_emp_id": f"Employee '{manager_emp_id}' must have Manager or Admin role."
                }
            )

        if manager.status != "Active":
            raise serializers.ValidationError(
                {"manager_emp_id": f"Manager '{manager_emp_id}' is not active."}
            )

        return manager


# ===========================================================
# BASE PROFILE SERIALIZER (DRY Principle)
# ===========================================================
class BaseProfileSerializer(serializers.ModelSerializer):
    """Base serializer for all profile types to reduce code duplication."""

    emp_id = serializers.CharField(source="user.emp_id", read_only=True)
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)
    email = serializers.EmailField(source="user.email", read_only=True)
    department = serializers.CharField(source="department.name", read_only=True)
    department_code = serializers.ReadOnlyField(source="department.code")
    role = serializers.CharField(source="user.role", read_only=True)
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "emp_id",
            "first_name",
            "last_name",
            "email",
            "role",
            "gender",
            "department",
            "department_code",
            "designation",
            "joining_date",
            "status",
            "contact_number",
            "dob",
            "profile_picture",
            "profile_picture_url",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pincode",
        ]
        read_only_fields = ["emp_id", "email", "department", "department_code", "role", "status"]

    def get_profile_picture_url(self, obj):
        """Generate absolute URL for profile picture."""
        request = self.context.get("request")
        if obj.profile_picture and hasattr(obj.profile_picture, "url"):
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        return None

    def validate_profile_picture(self, value):
        """Validate profile picture file."""
        return validate_image_file(value)

    def validate_dob(self, value):
        """Validate date of birth."""
        if value:
            today = date.today()
            age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))

            if value >= today:
                raise serializers.ValidationError("Date of birth cannot be today or in the future.")
            if age < 18:
                raise serializers.ValidationError("Employee must be at least 18 years old.")
            if age > 100:
                raise serializers.ValidationError("Please provide a valid date of birth.")
        return value

    def validate_pincode(self, value):
        """Validate Indian pincode."""
        if value and not re.match(r"^\d{6}$", value):
            raise serializers.ValidationError("Pincode must be exactly 6 digits.")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update profile with user data."""
        user_data = validated_data.pop("user", {})

        # Update user fields
        for field, value in user_data.items():
            setattr(instance.user, field, value)
        instance.user.save()

        # Update employee fields
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        return instance


# ===========================================================
# ROLE-SPECIFIC PROFILE SERIALIZERS
# ===========================================================
class AdminProfileSerializer(BaseProfileSerializer):
    """Admin profile with full access."""

    class Meta(BaseProfileSerializer.Meta):
        pass


class ManagerProfileSerializer(BaseProfileSerializer):
    """Manager profile with team management capabilities."""

    team_size = serializers.SerializerMethodField(read_only=True)

    class Meta(BaseProfileSerializer.Meta):
        fields = BaseProfileSerializer.Meta.fields + ["team_size"]

    def get_team_size(self, obj):
        """Count direct reports."""
        return Employee.objects.filter(manager=obj, status="Active").count()


class EmployeeProfileSerializer(BaseProfileSerializer):
    """Employee profile with manager information."""

    manager_name = serializers.SerializerMethodField()

    class Meta(BaseProfileSerializer.Meta):
        fields = BaseProfileSerializer.Meta.fields + [
            "project_name",
            "reporting_manager_name",
            "manager_name",
        ]

    def get_manager_name(self, obj):
        """Get manager's full name."""
        if obj.manager and hasattr(obj.manager, "user"):
            return (
                f"{obj.manager.user.first_name} {obj.manager.user.last_name}".strip()
                or "N/A"
            )
        return obj.reporting_manager_name or "Not Assigned"


# ===========================================================
# EMPLOYEE BULK CSV UPLOAD SERIALIZER
# ===========================================================
class EmployeeCSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    send_emails = serializers.BooleanField(default=True, required=False)

    def validate_file(self, value):
        """Validate CSV file."""
        if not value.name.endswith(".csv"):
            raise serializers.ValidationError("Only CSV files are allowed.")

        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("CSV file size must not exceed 5MB.")

        return value

    @transaction.atomic
    def create(self, validated_data):
        """Process bulk CSV upload with enhanced error handling."""
        file = validated_data["file"]
        send_emails = validated_data.get("send_emails", True)

        # Decode CSV file
        try:
            decoded_file = file.read().decode("utf-8")
        except UnicodeDecodeError:
            raise serializers.ValidationError(
                {"file": "Invalid CSV file encoding. Please use UTF-8."}
            )

        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        # Validate required columns
        required_cols = [
            "Emp Id",
            "First Name",
            "Last Name",
            "Email",
            "Dept Code",
            "Role",
            "Joining Date",
        ]
        optional_cols = ["Contact Number", "Designation", "Manager Emp Id"]

        if not reader.fieldnames:
            raise serializers.ValidationError(
                {"file": "CSV file is empty or has no headers."}
            )

        missing_cols = [col for col in required_cols if col not in reader.fieldnames]
        if missing_cols:
            raise serializers.ValidationError(
                {"file": f"Missing required columns: {', '.join(missing_cols)}"}
            )

        success_count = 0
        errors = []
        created_users = []  # Track for potential rollback

        # Cache departments for performance
        departments_cache = {
            dept.code.upper(): dept
            for dept in Department.objects.filter(is_active=True)
        }

        for i, row in enumerate(reader, start=2):
            try:
                # Extract and clean data
                emp_id = row.get("Emp Id", "").strip()
                email = row.get("Email", "").strip().lower()
                dept_code = row.get("Dept Code", "").strip().upper()
                first_name = row.get("First Name", "").strip()
                last_name = row.get("Last Name", "").strip()
                role = row.get("Role", "").strip().capitalize()
                joining_date_str = row.get("Joining Date", "").strip()
                contact_number = row.get("Contact Number", "").strip()
                designation = row.get("Designation", "").strip()
                manager_emp_id = row.get("Manager Emp Id", "").strip()

                # Validate mandatory fields
                if not all([emp_id, email, dept_code, role, first_name, last_name]):
                    errors.append(
                        f"Row {i}: Missing mandatory fields (Emp Id, First Name, Last Name, Email, Dept Code, Role)."
                    )
                    continue

                # Validate email format
                if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                    errors.append(f"Row {i}: Invalid email format '{email}'.")
                    continue

                # Check for duplicates
                if User.objects.filter(emp_id__iexact=emp_id).exists():
                    errors.append(f"Row {i}: Employee ID '{emp_id}' already exists.")
                    continue

                if User.objects.filter(email__iexact=email).exists():
                    errors.append(f"Row {i}: Email '{email}' already exists.")
                    continue

                # Validate department
                department = departments_cache.get(dept_code)
                if not department:
                    errors.append(
                        f"Row {i}: Department '{dept_code}' not found or inactive."
                    )
                    continue

                # Validate role
                valid_roles = ["Admin", "Manager", "Employee"]
                if role not in valid_roles:
                    errors.append(
                        f"Row {i}: Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}."
                    )
                    continue

                # Validate and parse joining date
                joining_date = None
                if joining_date_str:
                    try:
                        joining_date = datetime.strptime(joining_date_str, "%Y-%m-%d").date()
                        if joining_date > date.today():
                            errors.append(
                                f"Row {i}: Joining date cannot be in the future."
                            )
                            continue
                    except ValueError:
                        errors.append(
                            f"Row {i}: Invalid date format '{joining_date_str}'. Use YYYY-MM-DD."
                        )
                        continue

                # Validate contact number if provided
                if contact_number:
                    if not re.match(r"^\+91[6-9]\d{9}$", contact_number):
                        errors.append(
                            f"Row {i}: Invalid contact number format. Use +91XXXXXXXXXX."
                        )
                        continue

                # Validate manager if provided
                manager = None
                if manager_emp_id:
                    manager = Employee.objects.filter(
                        user__emp_id__iexact=manager_emp_id
                    ).first()
                    if not manager:
                        errors.append(
                            f"Row {i}: Manager '{manager_emp_id}' not found."
                        )
                        continue
                    if manager.user.role not in ["Manager", "Admin"]:
                        errors.append(
                            f"Row {i}: Manager '{manager_emp_id}' must have Manager or Admin role."
                        )
                        continue

                # Generate secure password
                temp_password = generate_secure_password()

                # Create user
                user = User.objects.create_user(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    department=department,
                )
                user.emp_id = emp_id
                user.set_password(temp_password)
                user.save()

                # Create employee
                employee = Employee.objects.create(
                    user=user,
                    department=department,
                    manager=manager,
                    joining_date=joining_date,
                    contact_number=contact_number or "",
                    designation=designation or "",
                    status="Active",
                )

                # Send welcome email
                if send_emails:
                    send_welcome_email(user, temp_password)

                created_users.append(
                    {
                        "emp_id": emp_id,
                        "email": email,
                        "temp_password": temp_password if not send_emails else "Sent via email",
                    }
                )
                success_count += 1

            except Exception as e:
                errors.append(f"Row {i}: Unexpected error - {str(e)}")

        # Prepare response
        response_data = {
            "success_count": success_count,
            "error_count": len(errors),
            "errors": errors[:50],  # Limit errors to first 50
        }

        if not send_emails and success_count > 0:
            response_data["created_users"] = created_users

        if len(errors) > 50:
            response_data["errors_truncated"] = True
            response_data["total_errors"] = len(errors)

        return response_data