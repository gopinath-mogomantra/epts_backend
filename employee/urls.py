# ===============================================
# employee/urls.py
# ===============================================
# URL routes for Department & Employee Management
# in the EPTS backend.
#
# Organized by module:
#  - Department Management (Admin only)
#  - Employee Management (Admin & Manager)
# ===============================================

from django.urls import path
from .views import (
    DepartmentListCreateView,
    DepartmentDetailView,
    EmployeeListView,
    EmployeeCreateView,
    EmployeeDetailView,
)

# ✅ Namespace for reverse URL lookups
app_name = "employee"

urlpatterns = [
    # ----------------------------------------------------------
    # 🏢 DEPARTMENT MANAGEMENT (Admin Only)
    # ----------------------------------------------------------
    # GET    /api/employee/departments/           → List all departments
    # POST   /api/employee/departments/           → Create a new department (Admin only)
    # GET    /api/employee/departments/<id>/      → Retrieve department details
    # PUT    /api/employee/departments/<id>/      → Update department info
    # DELETE /api/employee/departments/<id>/      → Delete department (if no employees)
    path("departments/", DepartmentListCreateView.as_view(), name="department-list-create"),
    path("departments/<int:pk>/", DepartmentDetailView.as_view(), name="department-detail"),

    # ----------------------------------------------------------
    # 👥 EMPLOYEE MANAGEMENT (Admin & Manager)
    # ----------------------------------------------------------
    # GET    /api/employee/employees/             → List all employees
    # POST   /api/employee/employees/create/      → Create a new employee (Admin/Manager)
    # GET    /api/employee/employees/<id>/        → Retrieve employee details
    # PUT    /api/employee/employees/<id>/        → Update employee info
    # DELETE /api/employee/employees/<id>/        → Delete employee (No Admin/Manager)
    path("employees/", EmployeeListView.as_view(), name="employee-list"),
    path("employees/create/", EmployeeCreateView.as_view(), name="employee-create"),
    path("employees/<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
]
