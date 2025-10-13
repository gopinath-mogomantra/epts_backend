# ===============================================
# employee/views.py
# ===============================================
# Contains all CRUD APIs for Department and Employee.
# Includes validation, permissions, and clean responses
# for React frontend integration.
# ===============================================

from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateSerializer,
    EmployeeUpdateSerializer
)
from users.models import Role
from users.serializers import UserSerializer


# ============================================================
# ✅ 1. DEPARTMENT LIST + CREATE VIEW
# ============================================================
class DepartmentListCreateView(generics.ListCreateAPIView):
    """
    GET: List all departments (Admin or Manager)
    POST: Create a new department (Admin only)
    """
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {"message": "Department created successfully.", "department": serializer.data},
            status=status.HTTP_201_CREATED
        )


# ============================================================
# ✅ 2. DEPARTMENT DETAIL VIEW (GET, PUT, DELETE)
# ============================================================
class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles individual Department operations.
    - GET: Retrieve department details
    - PUT/PATCH: Update department
    - DELETE: Remove department (Admin only)
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        # Prevent deletion if department has employees
        if instance.employees.exists():
            return Response(
                {"error": "Cannot delete department with assigned employees."},
                status=status.HTTP_400_BAD_REQUEST
            )
        self.perform_destroy(instance)
        return Response({"message": "Department deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


# ============================================================
# ✅ 3. EMPLOYEE LIST VIEW (ADMIN + MANAGER)
# ============================================================
class EmployeeListView(generics.ListAPIView):
    """
    Lists all employees with filters for department, manager, and status.
    Accessible to Admin and Manager roles.
    """
    queryset = Employee.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["department", "manager", "status"]
    search_fields = ["user__first_name", "user__last_name", "user__emp_id", "role_title"]
    ordering_fields = ["joining_date", "user__first_name"]

    def get_permissions(self):
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        # Managers only see their team members
        if hasattr(user, "employee_profile") and user.role.name.upper() == "MANAGER":
            return self.queryset.filter(manager=user.employee_profile)
        return self.queryset


# ============================================================
# ✅ 4. EMPLOYEE CREATE VIEW
# ============================================================
class EmployeeCreateView(generics.CreateAPIView):
    """
    Creates a new Employee + CustomUser entry.
    Accessible only by Admin or Manager.
    """
    serializer_class = EmployeeCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_role = getattr(request.user.role, "name", "").upper()

        # Only Admin or Manager can create employees
        if user_role not in ["ADMIN", "MANAGER"]:
            return Response(
                {"error": "You do not have permission to create employees."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            {
                "message": "Employee created successfully.",
                "employee": EmployeeSerializer(employee).data
            },
            status=status.HTTP_201_CREATED
        )


# ============================================================
# ✅ 5. EMPLOYEE DETAIL VIEW (GET, PUT, DELETE)
# ============================================================
class EmployeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete an employee.
    """
    queryset = Employee.objects.select_related("user", "department", "manager").all()
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_404(Employee, pk=self.kwargs["pk"])

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
            status=status.HTTP_200_OK
        )

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()

        # Prevent deleting Admin or Manager users
        if hasattr(employee.user.role, "name") and employee.user.role.name.upper() in ["ADMIN", "MANAGER"]:
            return Response(
                {"error": "You cannot delete Admin or Manager accounts."},
                status=status.HTTP_403_FORBIDDEN
            )

        employee.user.delete()
        employee.delete()
        return Response({"message": "Employee deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
