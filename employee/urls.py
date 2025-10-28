# ===========================================================
# employee/urls.py (Final — Frontend & Business Logic Aligned)
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, EmployeeViewSet, EmployeeCSVUploadView

app_name = "employee"

"""
Auto-registers all CRUD API endpoints for:
-------------------------------------------------------------
🔹 /api/employees/departments/  → Department CRUD (Admin only)
🔹 /api/employees/employees/    → Employee CRUD (Admin/Manager only)
🔹 /api/employees/upload_csv/   → Bulk employee upload (Admin only)
-------------------------------------------------------------
Each ViewSet supports standard REST actions:
  - GET (list, retrieve)
  - POST (create)
  - PUT/PATCH (update)
  - DELETE (soft delete / deactivate)
Custom routes:
  - /employees/team/<manager_emp_id>/
  - /employees/summary/
"""

# -----------------------------------------------------------
# 🔹 DRF Router Setup
# -----------------------------------------------------------
router = DefaultRouter()  # Add trailing_slash=False if Angular omits ending slashes
router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")

# -----------------------------------------------------------
# 🔹 URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    path("", include(router.urls)),

    # ✅ CSV Bulk Upload Endpoint (Admin only)
    path("upload_csv/", EmployeeCSVUploadView.as_view(), name="employee-csv-upload"),
]
