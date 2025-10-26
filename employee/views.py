# ===========================================================
# employee/views.py  (API Validation & Frontend Integration Ready)
# ===========================================================

from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from rest_framework.pagination import PageNumberPagination
from django.db import models

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateUpdateSerializer,
)

User = get_user_model()


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
    """CRUD APIs for departments."""
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    lookup_field = "code"
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "code"]
    ordering_fields = ["name", "created_at", "code"]

    def get_queryset(self):
        qs = super().get_queryset()
        include_inactive = self.request.query_params.get("include_inactive")
        user = self.request.user

        # Allow admins to view inactive departments if requested
        if include_inactive and include_inactive.lower() == "true":
            if user.is_superuser or getattr(user, "role", "") == "Admin":
                return qs
        return qs.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can create departments."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can update departments."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Soft delete (deactivate) department unless forced."""
        instance = self.get_object()
        if not (request.user.is_superuser or getattr(request.user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can delete departments."}, status=status.HTTP_403_FORBIDDEN)

        force_delete = request.query_params.get("force", "").lower() == "true"
        if force_delete:
            instance.delete()
            return Response({"message": f"🗑️ Department '{instance.name}' permanently deleted."}, status=status.HTTP_204_NO_CONTENT)

        if instance.employees.exists():
            return Response({"error": "Cannot delete department with active employees."}, status=status.HTTP_400_BAD_REQUEST)

        instance.is_active = False
        instance.save(update_fields=["is_active"])
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
    search_fields = ["user__first_name", "user__last_name", "user__emp_id", "designation", "contact_number", "department__name"]
    ordering_fields = ["joining_date", "user__first_name", "user__emp_id"]

    # --------------------------------------------------------
    # Serializer Switching
    # --------------------------------------------------------
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return EmployeeCreateUpdateSerializer
        return EmployeeSerializer

    # --------------------------------------------------------
    # Role-Based Query Filtering
    # --------------------------------------------------------
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, "role", "") == "Manager":
            return qs.filter(manager__user=user)
        elif getattr(user, "role", "") == "Employee":
            return qs.filter(user=user)
        return qs

    # --------------------------------------------------------
    # Object Fetching
    # --------------------------------------------------------
    def get_object(self):
        emp_id = self.kwargs.get("emp_id")
        try:
            return Employee.objects.select_related("user", "department", "manager").get(user__emp_id__iexact=emp_id)
        except Employee.DoesNotExist:
            raise NotFound(detail=f"Employee with emp_id '{emp_id}' not found.")

    # --------------------------------------------------------
    # CREATE EMPLOYEE
    # --------------------------------------------------------
    def create(self, request, *args, **kwargs):
        if not (request.user.is_superuser or getattr(request.user, "role", "") in ["Admin", "Manager"]):
            return Response({"error": "You do not have permission to create employees."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()
        return Response(
            {"message": "✅ Employee created successfully.", "employee": EmployeeSerializer(employee, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )

    # --------------------------------------------------------
    # UPDATE EMPLOYEE
    # --------------------------------------------------------
    def update(self, request, *args, **kwargs):
        employee = self.get_object()
        user = request.user

        # Managers can edit only their own team
        if getattr(user, "role", "") == "Manager" and employee.manager and employee.manager.user != user:
            return Response({"error": "Managers can update only their team members."}, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "✅ Employee updated successfully.", "employee": EmployeeSerializer(employee, context={"request": request}).data},
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------------
    # DELETE EMPLOYEE
    # --------------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        user = request.user

        if getattr(employee.user, "role", "") in ["Admin", "Manager"]:
            return Response({"error": "❌ Cannot delete Admin or Manager accounts."}, status=status.HTTP_403_FORBIDDEN)
        if not (user.is_superuser or getattr(user, "role", "") in ["Admin", "Manager"]):
            return Response({"error": "You do not have permission to delete employees."}, status=status.HTTP_403_FORBIDDEN)

        employee.user.delete()
        employee.delete()
        return Response({"message": "🗑️ Employee deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

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
