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
    path("departments/", DepartmentListCreateView.as_view(), name="department-list-create"),
    path("departments/<int:pk>/", DepartmentDetailView.as_view(), name="department-detail"),

    # ----------------------------------------------------------
    # 👥 EMPLOYEE MANAGEMENT (Admin & Manager)
    # ----------------------------------------------------------
    path("employees/", EmployeeListView.as_view(), name="employee-list"),
    path("employees/create/", EmployeeCreateView.as_view(), name="employee-create"),
    path("employees/<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
]
