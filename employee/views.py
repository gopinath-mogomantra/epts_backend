# ===========================================================
# employee/views.py (Final — Frontend & Business Logic Aligned)
# ===========================================================

from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework.pagination import PageNumberPagination
from django.db import models, transaction
import logging

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateUpdateSerializer,
    EmployeeCSVUploadSerializer,
)

User = get_user_model()
logger = logging.getLogger("employee")


# ===========================================================
# ✅ PAGINATION (Frontend Friendly)
# ===========================================================
class DefaultPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# ===========================================================
# ✅ DEPARTMENT VIEWSET
# ===========================================================
class DepartmentViewSet(viewsets.ModelViewSet):
    """CRUD APIs for departments (Admin-only create/update/delete)."""
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    lookup_field = "code"
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "code"]
    ordering_fields = ["name", "created_at", "code"]

    def get_queryset(self):
        qs = super().get_queryset()
        include_inactive = self.request.query_params.get("include_inactive", "").lower()
        user = self.request.user

        if include_inactive == "true" and (user.is_superuser or getattr(user, "role", "") == "Admin"):
            return qs
        return qs.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can create departments."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"Department created by {request.user.emp_id}")
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can update departments."}, status=status.HTTP_403_FORBIDDEN)
        logger.info(f"Department updated by {request.user.emp_id}")
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Soft delete (deactivate) department unless forced."""
        instance = self.get_object()
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can delete departments."}, status=status.HTTP_403_FORBIDDEN)

        force_delete = request.query_params.get("force", "").lower() == "true"
        if force_delete:
            instance.delete()
            logger.warning(f"Department {instance.name} permanently deleted by {request.user.emp_id}")
            return Response({"message": f"🗑️ Department '{instance.name}' permanently deleted."}, status=status.HTTP_204_NO_CONTENT)

        if instance.employees.filter(is_active=True).exists():
            return Response({"error": "Cannot deactivate department with active employees."}, status=status.HTTP_400_BAD_REQUEST)

        instance.is_active = False
        instance.save(update_fields=["is_active"])
        logger.info(f"Department {instance.name} deactivated by {request.user.emp_id}")
        return Response({"message": f"✅ Department '{instance.name}' deactivated successfully."}, status=status.HTTP_200_OK)


# ===========================================================
# ✅ EMPLOYEE VIEWSET
# ===========================================================
class EmployeeViewSet(viewsets.ModelViewSet):
    """Unified CRUD viewset for employees."""
    queryset = Employee.objects.select_related("user", "department", "manager").prefetch_related("team_members")
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DefaultPagination
    lookup_field = "emp_id"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["department", "manager", "status", "is_active"]
    search_fields = [
        "user__first_name", "user__last_name", "user__emp_id",
        "designation", "phone", "department__name"
    ]
    ordering_fields = ["joining_date", "user__first_name", "user__emp_id"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return EmployeeCreateUpdateSerializer
        return EmployeeSerializer

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, "role", "") == "Manager":
            return qs.filter(manager__user=user)
        elif getattr(user, "role", "") == "Employee":
            return qs.filter(user=user)
        return qs

    def get_object(self):
        emp_id = self.kwargs.get("emp_id")
        try:
            return Employee.objects.select_related("user", "department", "manager").get(user__emp_id__iexact=emp_id)
        except Employee.DoesNotExist:
            raise NotFound(detail=f"Employee with emp_id '{emp_id}' not found.")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", "") in ["Admin", "Manager"]):
            return Response({"error": "You do not have permission to create employees."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        logger.info(f"Employee {employee.emp_id} created by {request.user.emp_id}")

        return Response(
            {
                "message": "✅ Employee created successfully.",
                "employee": EmployeeSerializer(employee, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        employee = self.get_object()
        user = request.user

        if getattr(user, "role", "") == "Manager" and employee.manager and employee.manager.user != user:
            return Response({"error": "Managers can update only their own team members."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(employee, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"Employee {employee.emp_id} updated by {user.emp_id}")

        return Response(
            {
                "message": "✅ Employee updated successfully.",
                "employee": EmployeeSerializer(employee, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        user = request.user

        if getattr(employee.user, "role", "") in ["Admin", "Manager"]:
            return Response({"error": "❌ Cannot delete Admin or Manager accounts."}, status=status.HTTP_403_FORBIDDEN)
        if not (user.is_superuser or getattr(user, "role", "") in ["Admin", "Manager"]):
            return Response({"error": "You do not have permission to delete employees."}, status=status.HTTP_403_FORBIDDEN)

        employee.deactivate()
        employee.user.is_active = False
        employee.user.save(update_fields=["is_active"])
        logger.warning(f"Employee {employee.emp_id} deactivated by {user.emp_id}")

        return Response(
            {"message": f"🟡 Employee '{employee.user.emp_id}' deactivated successfully."},
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------------
    # TEAM MEMBERS (Paginated)
    # --------------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"team/(?P<manager_emp_id>[^/.]+)")
    def get_team(self, request, manager_emp_id=None):
        """Return paginated list of team members under given manager."""
        try:
            manager = Employee.objects.select_related("user", "department").get(user__emp_id__iexact=manager_emp_id)
        except Employee.DoesNotExist:
            return Response({"error": f"Manager '{manager_emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        if manager.user.role != "Manager":
            return Response({"error": f"User '{manager_emp_id}' is not a Manager."}, status=status.HTTP_400_BAD_REQUEST)

        team = Employee.objects.filter(manager=manager).select_related("user", "department")
        status_filter = request.query_params.get("status")
        dept_code = request.query_params.get("department_code")
        search_query = request.query_params.get("search")

        if status_filter:
            team = team.filter(status__iexact=status_filter)
        if dept_code:
            team = team.filter(department__code__iexact=dept_code)
        if search_query:
            team = team.filter(
                models.Q(user__first_name__icontains=search_query)
                | models.Q(user__last_name__icontains=search_query)
                | models.Q(designation__icontains=search_query)
            )

        paginator = DefaultPagination()
        paginated_team = paginator.paginate_queryset(team, request)
        team_data = [
            {
                "emp_id": e.user.emp_id,
                "name": f"{e.user.first_name} {e.user.last_name}".strip(),
                "designation": e.designation,
                "department": e.department.name if e.department else None,
                "status": e.status,
            }
            for e in paginated_team
        ]

        return paginator.get_paginated_response({
            "manager": {
                "emp_id": manager.user.emp_id,
                "name": f"{manager.user.first_name} {manager.user.last_name}".strip(),
                "department": manager.department.name if manager.department else None,
                "designation": manager.designation,
            },
            "total_team_members": team.count(),
            "team_members": team_data,
        })

    # --------------------------------------------------------
    # HR DASHBOARD SUMMARY
    # --------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """HR/Admin summary of department and employee stats."""
        total_employees = Employee.objects.count()
        active_employees = Employee.objects.filter(is_active=True).count()
        on_leave = Employee.objects.filter(status="On Leave").count()
        resigned = Employee.objects.filter(status="Resigned").count()
        managers = Employee.objects.filter(role="Manager", is_active=True).count()

        departments = Department.objects.filter(is_active=True)
        dept_summary = [
            {
                "department": d.name,
                "code": d.code,
                "active_employees": d.employees.filter(is_active=True).count(),
                "total_employees": d.employees.count(),
            }
            for d in departments
        ]

        return Response({
            "summary": {
                "total_employees": total_employees,
                "active_employees": active_employees,
                "on_leave": on_leave,
                "resigned": resigned,
                "total_managers": managers,
            },
            "departments": dept_summary,
        }, status=status.HTTP_200_OK)


# ===========================================================
# ✅ EMPLOYEE BULK CSV UPLOAD API
# ===========================================================
class EmployeeCSVUploadView(APIView):
    """Upload and process a CSV file to bulk-create employees."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can upload employee CSV files."}, status=status.HTTP_403_FORBIDDEN)

        serializer = EmployeeCSVUploadSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            logger.info(f"CSV upload processed by {request.user.emp_id}")
            return Response(
                {
                    "message": "✅ Employee CSV processed successfully.",
                    "uploaded_count": result["success_count"],
                    "errors": result["errors"],
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
