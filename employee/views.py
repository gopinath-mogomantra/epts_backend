# ===========================================================
# employee/views.py (Enhanced Version — 01-Nov-2025)
# ===========================================================

from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError, PermissionDenied
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework.pagination import PageNumberPagination
from django.db import models, transaction
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from django.core.cache import cache
import logging

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateUpdateSerializer,
    EmployeeCSVUploadSerializer,
    AdminProfileSerializer,
    ManagerProfileSerializer,
    EmployeeProfileSerializer,
)

User = get_user_model()
logger = logging.getLogger("employee")


# ===========================================================
# CUSTOM PERMISSIONS
# ===========================================================
class IsAdminUser(permissions.BasePermission):
    """Permission class for Admin-only access."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser or getattr(request.user, "role", "") == "Admin"
        )


class IsManagerOrAdmin(permissions.BasePermission):
    """Permission class for Manager or Admin access."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser
            or getattr(request.user, "role", "") in ["Admin", "Manager"]
        )


class IsOwnerOrManager(permissions.BasePermission):
    """Permission class to allow users to access/edit their own data or their manager."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = getattr(user, "role", "")

        # Admins have full access
        if user.is_superuser or role == "Admin":
            return True

        # Managers can access their team members
        if role == "Manager":
            try:
                manager_employee = user.employee_profile
                return obj.manager == manager_employee
            except AttributeError:
                return False

        # Employees can only access their own profile
        return obj.user == user


# ===========================================================
# PAGINATION
# ===========================================================
class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        """Enhanced pagination response with metadata."""
        return Response(
            {
                "count": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.page_size,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
            }
        )


# ===========================================================
# DEPARTMENT VIEWSET
# ===========================================================
class DepartmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Department CRUD operations.
    
    Permissions:
    - List/Retrieve: All authenticated users
    - Create/Update/Delete: Admin only
    """

    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    lookup_field = "code"
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "code"]
    ordering_fields = ["name", "created_at", "code", "employee_count"]
    filterset_fields = ["is_active"]

    def get_queryset(self):
        """Optimize queryset with employee count annotation."""
        qs = super().get_queryset()

        # Annotate employee count for performance
        qs = qs.annotate(
            _employee_count=Count(
                "employees", filter=Q(employees__status="Active", employees__is_deleted=False)
            )
        )

        # Filter inactive departments for non-admins
        include_inactive = self.request.query_params.get("include_inactive", "").lower()
        user = self.request.user
        is_admin = user.is_superuser or getattr(user, "role", "") == "Admin"

        if not (include_inactive == "true" and is_admin):
            qs = qs.filter(is_active=True)

        return qs

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Create new department with logging."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department = serializer.save()

        logger.info(
            f"🏢 Department '{department.name}' ({department.code}) created by {request.user.username}"
        )

        # Clear department cache
        cache.delete("departments_list")

        return Response(
            {
                "message": "Department created successfully.",
                "department": DepartmentSerializer(department, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        """Update department with logging."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        department = serializer.save()

        logger.info(
            f"🏢 Department '{department.name}' updated by {request.user.username}"
        )

        # Clear cache
        cache.delete("departments_list")
        cache.delete(f"department_{instance.code}")

        return Response(
            {
                "message": "Department updated successfully.",
                "department": DepartmentSerializer(department, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Soft delete or permanent delete department.
        
        Query params:
        - force=true: Permanent deletion (use with caution)
        - Default: Soft delete (deactivate)
        """
        instance = self.get_object()
        force_delete = request.query_params.get("force", "").lower() == "true"

        # Check for active employees
        active_employees = Employee.objects.filter(
            department=instance, status="Active", is_deleted=False
        )
        active_count = active_employees.count()

        if active_count > 0 and not force_delete:
            return Response(
                {
                    "error": f"Cannot deactivate department with {active_count} active employee(s).",
                    "detail": "Please reassign or deactivate employees first, or use force=true parameter.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if force_delete:
            dept_name = instance.name
            dept_code = instance.code

            # Reassign employees to null department (or handle as per business logic)
            if active_count > 0:
                active_employees.update(department=None)
                logger.warning(
                    f"{active_count} employees unassigned from department '{dept_name}'"
                )

            instance.delete()
            logger.warning(
                f"🗑️ Department '{dept_name}' ({dept_code}) permanently deleted by {request.user.username}"
            )

            # Clear cache
            cache.delete("departments_list")
            cache.delete(f"department_{dept_code}")

            return Response(
                {"message": f"Department '{dept_name}' permanently deleted."},
                status=status.HTTP_204_NO_CONTENT,
            )

        # Soft delete (deactivate)
        instance.is_active = False
        instance.save(update_fields=["is_active"])

        logger.info(
            f"Department '{instance.name}' deactivated by {request.user.username}"
        )

        # Clear cache
        cache.delete("departments_list")

        return Response(
            {"message": f"Department '{instance.name}' deactivated successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def employees(self, request, code=None):
        """Get all employees in a department."""
        department = self.get_object()
        employees = Employee.objects.filter(
            department=department, is_deleted=False
        ).select_related("user", "manager")

        # Apply status filter if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            employees = employees.filter(status__iexact=status_filter)

        serializer = EmployeeSerializer(
            employees, many=True, context={"request": request}
        )

        return Response(
            {
                "department": department.name,
                "department_code": department.code,
                "employee_count": employees.count(),
                "employees": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get department statistics (Admin only)."""
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            raise PermissionDenied("Only admins can view statistics.")

        departments = Department.objects.annotate(
            active_employees=Count(
                "employees",
                filter=Q(employees__status="Active", employees__is_deleted=False),
            ),
            total_employees=Count("employees", filter=Q(employees__is_deleted=False)),
        ).order_by("-active_employees")

        stats = []
        for dept in departments:
            stats.append(
                {
                    "id": dept.id,
                    "name": dept.name,
                    "code": dept.code,
                    "is_active": dept.is_active,
                    "active_employees": dept.active_employees,
                    "total_employees": dept.total_employees,
                }
            )

        return Response(
            {
                "total_departments": departments.count(),
                "active_departments": departments.filter(is_active=True).count(),
                "departments": stats,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# EMPLOYEE VIEWSET
# ===========================================================
class EmployeeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Employee CRUD operations.
    
    Permissions:
    - Admin: Full access to all employees
    - Manager: Access to their team members
    - Employee: Access to their own profile only
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DefaultPagination
    lookup_field = "emp_id"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "department__code", "user__role"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__emp_id",
        "user__email",
        "designation",
        "contact_number",
        "department__name",
        "department__code",
    ]
    ordering_fields = ["joining_date", "user__first_name", "user__emp_id", "created_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ["create", "update", "partial_update"]:
            return EmployeeCreateUpdateSerializer
        return EmployeeSerializer

    def get_queryset(self):
        """
        Return filtered queryset based on user role.
        
        Optimizations:
        - select_related for foreign keys
        - prefetch_related for reverse foreign keys
        - annotate team_size for managers
        """
        user = self.request.user
        role = getattr(user, "role", "")

        # Base queryset with optimizations
        qs = Employee.objects.select_related(
            "user", "department", "manager", "manager__user"
        ).filter(is_deleted=False)

        # Annotate team size
        qs = qs.annotate(
            _team_size=Count(
                "team_members", filter=Q(team_members__status="Active", team_members__is_deleted=False)
            )
        )

        # Role-based filtering
        if role == "Manager":
            # Managers see only their team members
            qs = qs.filter(manager__user=user)
        elif role == "Employee":
            # Employees see only themselves
            qs = qs.filter(user=user)
        # Admins see all employees (no filter)

        # Apply custom filters
        qs = self._apply_custom_filters(qs)

        return qs

    def _apply_custom_filters(self, qs):
        """Apply custom query parameter filters."""
        request = self.request

        # Department filter (by name, code, or ID)
        department_param = request.query_params.get("department")
        if department_param:
            dept_qs = Department.objects.filter(
                Q(name__iexact=department_param)
                | Q(code__iexact=department_param)
                | Q(id=department_param)
            )
            dept = dept_qs.first()
            if dept:
                qs = qs.filter(department=dept)
            else:
                # Partial match on department name
                qs = qs.filter(department__name__icontains=department_param)

        # Manager filter
        manager_param = request.query_params.get("manager")
        if manager_param:
            manager_emp = Employee.objects.select_related("user").filter(
                Q(user__emp_id__iexact=manager_param) | Q(user__email__iexact=manager_param)
            ).first()
            if manager_emp:
                qs = qs.filter(manager=manager_emp)
            else:
                qs = qs.none()

        # Joining date range filter
        joining_from = request.query_params.get("joining_from")
        joining_to = request.query_params.get("joining_to")
        if joining_from:
            qs = qs.filter(joining_date__gte=joining_from)
        if joining_to:
            qs = qs.filter(joining_date__lte=joining_to)

        return qs

    def get_object(self):
        """Retrieve employee by emp_id with optimizations."""
        emp_id = self.kwargs.get("emp_id")

        try:
            employee = (
                Employee.objects.select_related("user", "department", "manager", "manager__user")
                .annotate(
                    _team_size=Count(
                        "team_members",
                        filter=Q(team_members__status="Active", team_members__is_deleted=False),
                    )
                )
                .get(user__emp_id__iexact=emp_id)
            )

            if employee.is_deleted:
                raise ValidationError(
                    "This employee has been deleted. No further actions allowed."
                )

            # Check object-level permissions
            self.check_object_permissions(self.request, employee)

            return employee

        except Employee.DoesNotExist:
            raise NotFound(detail=f"Employee with emp_id '{emp_id}' not found.")

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action == "create":
            return [IsManagerOrAdmin()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAuthenticated(), IsOwnerOrManager()]
        return [permissions.IsAuthenticated()]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Create new employee with comprehensive validation."""
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        employee.refresh_from_db()

        logger.info(
            f"👤 Employee '{employee.user.emp_id}' ({employee.user.email}) created by {request.user.username}"
        )

        # Clear cache
        cache.delete("employees_list")

        return Response(
            {
                "message": "Employee created successfully.",
                "employee": EmployeeSerializer(employee, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update employee with validation."""
        partial = kwargs.pop("partial", False)
        employee = self.get_object()

        if employee.is_deleted:
            return Response(
                {"error": "This employee has been deleted. No updates allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(
            employee, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_employee = serializer.save()
        updated_employee.refresh_from_db()

        logger.info(
            f"✏️ Employee '{updated_employee.user.emp_id}' updated by {request.user.username}"
        )

        # Clear cache
        cache.delete(f"employee_{employee.user.emp_id}")

        return Response(
            {
                "message": "Employee updated successfully.",
                "employee": EmployeeSerializer(
                    updated_employee, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Soft delete employee.
        
        Business rules:
        - Cannot delete Admin or Manager accounts
        - Only Admin/Manager can delete employees
        """
        employee = self.get_object()
        user = request.user

        if employee.is_deleted:
            return Response(
                {"error": "This employee is already deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent deletion of Admin/Manager accounts
        employee_role = getattr(employee.user, "role", "")
        if employee_role in ["Admin", "Manager"]:
            return Response(
                {
                    "error": f"Cannot delete {employee_role} accounts.",
                    "detail": "Please change their role to Employee first, or contact system administrator.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Perform soft delete
        employee.soft_delete()

        logger.warning(
            f"🗑️ Employee '{employee.user.emp_id}' ({employee.user.email}) soft-deleted by {user.username}"
        )

        # Clear cache
        cache.delete(f"employee_{employee.user.emp_id}")
        cache.delete("employees_list")

        return Response(
            {"message": f"Employee '{employee.user.emp_id}' deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def team(self, request, emp_id=None):
        """Get team members for a manager."""
        employee = self.get_object()

        # Only managers and admins can view teams
        user_role = getattr(request.user, "role", "")
        if user_role not in ["Admin", "Manager"]:
            raise PermissionDenied("Only managers and admins can view team information.")

        team_members = Employee.objects.filter(
            manager=employee, is_deleted=False
        ).select_related("user", "department")

        serializer = EmployeeSerializer(
            team_members, many=True, context={"request": request}
        )

        return Response(
            {
                "manager": {
                    "emp_id": employee.user.emp_id,
                    "name": f"{employee.user.first_name} {employee.user.last_name}",
                    "designation": employee.designation,
                },
                "team_size": team_members.count(),
                "team_members": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        """Get employee statistics (Admin only)."""
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            raise PermissionDenied("Only admins can view statistics.")

        total_employees = Employee.objects.filter(is_deleted=False).count()
        active_employees = Employee.objects.filter(
            status="Active", is_deleted=False
        ).count()
        inactive_employees = total_employees - active_employees

        # Role distribution
        role_stats = (
            Employee.objects.filter(is_deleted=False)
            .values("user__role")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Department distribution
        dept_stats = (
            Employee.objects.filter(is_deleted=False)
            .values("department__name", "department__code")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        return Response(
            {
                "total_employees": total_employees,
                "active_employees": active_employees,
                "inactive_employees": inactive_employees,
                "by_role": list(role_stats),
                "by_department": list(dept_stats),
                "last_updated": timezone.now(),
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# PROFILE VIEWS (Role-Specific)
# ===========================================================
class BaseProfileView(APIView):
    """Base class for profile views to reduce code duplication."""

    permission_classes = [permissions.IsAuthenticated]
    required_role = None
    serializer_class = None

    def get_employee(self, user):
        """Get employee profile for user."""
        employee = getattr(user, "employee_profile", None)
        if not employee:
            raise NotFound("Employee record not found.")
        return employee

    def check_role(self, user):
        """Check if user has required role."""
        user_role = getattr(user, "role", "")
        if self.required_role and user_role != self.required_role:
            raise PermissionDenied(f"Only {self.required_role}s can access this API.")

    def get(self, request):
        """Get profile data."""
        self.check_role(request.user)
        employee = self.get_employee(request.user)
        serializer = self.serializer_class(employee, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @transaction.atomic
    def patch(self, request):
        """Update profile data."""
        self.check_role(request.user)
        employee = self.get_employee(request.user)

        serializer = self.serializer_class(
            employee, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_employee = serializer.save()

        logger.info(f"👤 {self.required_role} '{request.user.username}' updated their profile.")

        # Clear cache
        cache.delete(f"profile_{request.user.emp_id}")

        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        """Alias for patch (full update)."""
        return self.patch(request)


class AdminProfileView(BaseProfileView):
    """Admin profile management."""

    required_role = "Admin"
    serializer_class = AdminProfileSerializer


class ManagerProfileView(BaseProfileView):
    """Manager profile management."""

    required_role = "Manager"
    serializer_class = ManagerProfileSerializer


class EmployeeProfileView(BaseProfileView):
    """Employee profile management."""

    required_role = "Employee"
    serializer_class = EmployeeProfileSerializer


# ===========================================================
# EMPLOYEE BULK CSV UPLOAD VIEW
# ===========================================================
class EmployeeCSVUploadView(APIView):
    """
    Bulk upload employees via CSV file.
    
    Permissions: Admin only
    
    Request format: multipart/form-data
    Fields:
    - file: CSV file
    - send_emails: boolean (optional, default: true)
    """

    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """Process CSV upload and create employees."""
        serializer = EmployeeCSVUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()

        success_count = result.get("success_count", 0)
        error_count = result.get("error_count", 0)
        errors = result.get("errors", [])

        logger.info(
            f"📊 CSV upload processed by {request.user.username}: "
            f"{success_count} success, {error_count} errors"
        )

        # Clear cache
        if success_count > 0:
            cache.delete("employees_list")

        response_data = {
            "message": "Employee CSV processed successfully.",
            "summary": {
                "uploaded_count": success_count,
                "error_count": error_count,
                "total_processed": success_count + error_count,
            },
        }

        # Include errors if any
        if errors:
            response_data["errors"] = errors
            if result.get("errors_truncated"):
                response_data["errors_truncated"] = True
                response_data["total_errors"] = result.get("total_errors")

        # Include created users if emails weren't sent
        if "created_users" in result:
            response_data["created_users"] = result["created_users"]
            response_data[
                "warning"
            ] = "Temporary passwords are included. Please distribute securely."

        # Set appropriate status code
        response_status = status.HTTP_201_CREATED if success_count > 0 else status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=response_status)


# ===========================================================
# HEALTH CHECK VIEW (Optional)
# ===========================================================
class HealthCheckView(APIView):
    """Health check endpoint for monitoring."""

    permission_classes = []

    def get(self, request):
        """Simple health check."""
        return Response(
            {
                "status": "healthy",
                "timestamp": timezone.now(),
                "service": "Employee Management API",
            },
            status=status.HTTP_200_OK,
        )