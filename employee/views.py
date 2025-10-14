# ===============================================
# employee/views.py
# ===============================================
# CRUD APIs for Department and Employee modules.
# Includes search, filter, ordering, and role-based access.
# ===============================================

from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.contrib.auth import get_user_model

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateSerializer,
    EmployeeUpdateSerializer,
)

User = get_user_model()


# ============================================================
# ✅ 1. DEPARTMENT LIST + CREATE VIEW
# ============================================================
class DepartmentListCreateView(generics.ListCreateAPIView):
    """
    GET: List all departments (Admin/Manager)
    POST: Create a new department (Admin only)
    """
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Allow Managers to view departments,
        but restrict creation to Admins.
        """
        queryset = super().get_queryset()
        if not self.request.user.is_authenticated:
            return Department.objects.none()
        return queryset

    def post(self, request, *args, **kwargs):
        if request.user.role != "Admin" and not request.user.is_superuser:
            return Response(
                {"error": "Only Admins can create departments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department = serializer.save()

        return Response(
            {
                "message": "✅ Department created successfully.",
                "department": DepartmentSerializer(department).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# ✅ 2. DEPARTMENT DETAIL VIEW (GET, PUT, DELETE)
# ============================================================
class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles CRUD operations on a single Department.
    Only Admins can delete; Managers can view/edit.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()

        # Prevent deletion if department has employees
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

        self.perform_destroy(instance)
        return Response(
            {"message": "🗑️ Department deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )


# ============================================================
# ✅ 3. EMPLOYEE LIST VIEW (ADMIN + MANAGER)
# ============================================================
class EmployeeListView(generics.ListAPIView):
    """
    Lists employees:
    - Admins: Can view all employees
    - Managers: Can view only their team members
    """
    queryset = Employee.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["department", "manager", "status"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__emp_id",
        "designation",
    ]
    ordering_fields = ["date_joined", "user__first_name"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # Managers can view only their team members
        if user.role == "Manager":
            return queryset.filter(manager__user=user)

        return queryset


# ============================================================
# ✅ 4. EMPLOYEE CREATE VIEW (ADMIN + MANAGER)
# ============================================================
class EmployeeCreateView(generics.CreateAPIView):
    """
    Create a new Employee (linked User created internally).
    Accessible by Admins and Managers.
    """
    serializer_class = EmployeeCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.role not in ["Admin", "Manager"] and not request.user.is_superuser:
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
                "employee": EmployeeSerializer(employee).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# ✅ 5. EMPLOYEE DETAIL VIEW (GET, PUT, DELETE)
# ============================================================
class EmployeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete an employee record.
    Admins: Full access.
    Managers: Limited to their team.
    Employees: Read-only self access.
    """
    queryset = Employee.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        employee = get_object_or_404(Employee, pk=self.kwargs["pk"])
        user = self.request.user

        # Managers: Only view or edit their team
        if user.role == "Manager" and employee.manager and employee.manager.user != user:
            raise permissions.PermissionDenied("Managers can access only their team members.")

        # Employees: Only view their own record
        if user.role == "Employee" and employee.user != user:
            raise permissions.PermissionDenied("Employees can view only their own profile.")

        return employee

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return EmployeeUpdateSerializer
        return EmployeeSerializer

    def put(self, request, *args, **kwargs):
        employee = self.get_object()
        serializer = self.get_serializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "✅ Employee updated successfully.",
                "employee": EmployeeSerializer(employee).data,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()

        # Restrict deletion of privileged roles
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
