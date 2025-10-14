# ===============================================
# employee/views.py
# ===============================================
# CRUD APIs for Department and Employee modules.
# Role-based access for Admins and Managers.
# ===============================================

from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateSerializer,
    EmployeeUpdateSerializer,
)
from django.contrib.auth import get_user_model

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

    def post(self, request, *args, **kwargs):
        # Only Admins can create new departments
        if request.user.role != "Admin" and not request.user.is_superuser:
            return Response(
                {"error": "Only Admins can create departments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department = serializer.save()

        return Response(
            {"message": "Department created successfully.", "department": DepartmentSerializer(department).data},
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# ✅ 2. DEPARTMENT DETAIL VIEW (GET, PUT, DELETE)
# ============================================================
class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles individual Department CRUD.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        # Prevent deletion if department has employees
        if instance.employees.exists():
            return Response(
                {"error": "Cannot delete a department that has assigned employees."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only Admins can delete
        if request.user.role != "Admin" and not request.user.is_superuser:
            return Response(
                {"error": "Only Admins can delete departments."},
                status=status.HTTP_403_FORBIDDEN,
            )

        self.perform_destroy(instance)
        return Response({"message": "Department deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


# ============================================================
# ✅ 3. EMPLOYEE LIST VIEW (ADMIN + MANAGER)
# ============================================================
class EmployeeListView(generics.ListAPIView):
    """
    Lists all employees.
    - Admins: Can view all employees
    - Managers: Can view only their team
    """
    queryset = Employee.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["department", "manager", "status"]
    search_fields = ["user__first_name", "user__last_name", "user__emp_id", "designation"]
    ordering_fields = ["date_joined", "user__first_name"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        # Managers only see their team members
        if user.role == "Manager":
            return queryset.filter(manager__user=user)

        return queryset


# ============================================================
# ✅ 4. EMPLOYEE CREATE VIEW (ADMIN + MANAGER)
# ============================================================
class EmployeeCreateView(generics.CreateAPIView):
    """
    Create a new Employee + User entry.
    Accessible by Admin and Manager only.
    """
    serializer_class = EmployeeCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # Only Admins and Managers can create employees
        if request.user.role not in ["Admin", "Manager"] and not request.user.is_superuser:
            return Response(
                {"error": "You do not have permission to create employees."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            {"message": "Employee created successfully.", "employee": EmployeeSerializer(employee).data},
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# ✅ 5. EMPLOYEE DETAIL VIEW (GET, PUT, DELETE)
# ============================================================
class EmployeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete an employee.
    Admins can modify all; Managers only their team.
    """
    queryset = Employee.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        employee = get_object_or_404(Employee, pk=self.kwargs["pk"])

        # Managers can only access their team
        if self.request.user.role == "Manager" and employee.manager and employee.manager.user != self.request.user:
            return Response(
                {"error": "You do not have permission to access this employee."},
                status=status.HTTP_403_FORBIDDEN,
            )
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
            {"message": "Employee updated successfully.", "employee": EmployeeSerializer(employee).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()

        # Prevent deletion of Admin or Manager accounts
        if employee.user.role in ["Admin", "Manager"]:
            return Response(
                {"error": "You cannot delete Admin or Manager accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        employee.user.delete()
        employee.delete()
        return Response({"message": "Employee deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
