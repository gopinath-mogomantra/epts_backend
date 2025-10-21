# ===============================================
# employee/views.py
# ===============================================
# Final Updated Version — Clean, Secure, and Optimized
# ===============================================

from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateUpdateSerializer,
)

User = get_user_model()


# ============================================================
# ✅ 1. DEPARTMENT VIEWSET
# ============================================================
class DepartmentViewSet(viewsets.ModelViewSet):
    """
    Handles CRUD operations for Departments.
    Admins can create, update, delete.
    Managers and Employees can only view.
    """
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Show only active departments by default."""
        qs = super().get_queryset()
        return qs.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        if request.user.role != "Admin" and not request.user.is_superuser:
            return Response(
                {"error": "Only Admins can create departments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.employees.exists():
            return Response(
                {"error": "Cannot delete a department with assigned employees."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.user.role != "Admin" and not request.user.is_superuser:
            return Response(
                {"error": "Only Admins can delete departments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.is_active = False
        instance.save()
        return Response(
            {"message": "🗑️ Department deactivated successfully."},
            status=status.HTTP_200_OK,
        )


# ============================================================
# ✅ 2. EMPLOYEE VIEWSET
# ============================================================
class EmployeeViewSet(viewsets.ModelViewSet):
    """
    Unified CRUD ViewSet for Employees.
    - Admins: Full access
    - Managers: Access to their team
    - Employees: Can view their own record only
    """
    queryset = Employee.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["department", "manager", "status"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__emp_id",
        "designation",
        "contact_number",
    ]
    ordering_fields = ["joining_date", "user__first_name", "user__emp_id"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if user.role == "Manager":
            return queryset.filter(manager__user=user)
        elif user.role == "Employee":
            return queryset.filter(user=user)
        return queryset

    def get_serializer_class(self):
        """Use write serializer for POST/PUT/PATCH"""
        if self.action in ["create", "update", "partial_update"]:
            return EmployeeCreateUpdateSerializer
        return EmployeeSerializer

    def create(self, request, *args, **kwargs):
        user = request.user
        if user.role not in ["Admin", "Manager"] and not user.is_superuser:
            return Response(
                {"error": "You do not have permission to create employees."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            {
                "message": "✅ Employee created successfully.",
                "employee": EmployeeSerializer(employee, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "✅ Employee updated successfully.",
                "employee": EmployeeSerializer(employee, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()

        if employee.user.role in ["Admin", "Manager"]:
            return Response(
                {"error": "❌ Cannot delete Admin or Manager accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee.user.delete()
        employee.delete()
        return Response(
            {"message": "🗑️ Employee deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )

    def retrieve(self, request, *args, **kwargs):
        """Restrict visibility: employees see only their own data"""
        employee = self.get_object()
        user = request.user

        if user.role == "Manager" and employee.manager and employee.manager.user != user:
            return Response(
                {"error": "Managers can view only their team members."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.role == "Employee" and employee.user != user:
            return Response(
                {"error": "Employees can view only their own record."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(employee)
        return Response(serializer.data)
