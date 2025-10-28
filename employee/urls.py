# ===========================================================
# employee/urls.py ✅ (Frontend-Aligned & Production-Ready)
# Employee Performance Tracking System (EPTS)
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, EmployeeViewSet, EmployeeCSVUploadView

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
🔹 /api/employee/departments/   → Department CRUD (Admin only)
🔹 /api/employee/employees/     → Employee CRUD (Admin/Manager only)
🔹 /api/employee/upload_csv/    → Bulk employee upload (Admin only)
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
]
