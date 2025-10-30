# ===========================================================
# employee/urls.py ✅ Final — Admin + Manager + Employee Profiles Ready
# Employee Performance Tracking System (EPTS)
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet,
    EmployeeViewSet,
    EmployeeCSVUploadView,
    AdminProfileView,
    ManagerProfileView,
    EmployeeProfileView,  # ✅ NEW
)

# -----------------------------------------------------------
# 🌐 App Namespace
# -----------------------------------------------------------
app_name = "employee"

# -----------------------------------------------------------
# 📘 ROUTE SUMMARY
# -----------------------------------------------------------
"""
Auto-registers all CRUD API endpoints for:
-------------------------------------------------------------
🔹 /api/employee/departments/        → Department CRUD (Admin only)
🔹 /api/employee/employees/          → Employee CRUD (Admin/Manager only)
🔹 /api/employee/upload_csv/         → Bulk employee upload (Admin only)
🔹 /api/employee/admin/profile/      → Admin personal profile view/update
🔹 /api/employee/manager/profile/    → Manager personal profile view/update
🔹 /api/employee/profile/            → Employee personal profile view/update
-------------------------------------------------------------
Each ViewSet supports:
  - GET (list, retrieve)
  - POST (create)
  - PUT/PATCH (update)
  - DELETE (soft delete / deactivate)

Custom routes within ViewSets may include:
  - /api/employee/employees/team/<manager_emp_id>/
  - /api/employee/employees/summary/
"""

# -----------------------------------------------------------
# 🚀 DRF Router Configuration
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")

# -----------------------------------------------------------
# 🛠️ URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    # 🔹 Auto-generated CRUD Endpoints
    path("", include(router.urls)),

    # 🔹 Bulk Employee CSV Upload
    path("upload_csv/", EmployeeCSVUploadView.as_view(), name="employee_csv_upload"),

    # 🔹 Profile APIs (role-based)
    path("admin/profile/", AdminProfileView.as_view(), name="admin_profile"),
    path("manager/profile/", ManagerProfileView.as_view(), name="manager_profile"),
    path("profile/", EmployeeProfileView.as_view(), name="employee_profile"),  # ✅ NEW
]
