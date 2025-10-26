# ===========================================================
# employee/urls.py (Final Updated — Frontend-Aligned & API-Ready)
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, EmployeeViewSet

app_name = "employee"

"""
Auto-registers all CRUD API endpoints for:
-------------------------------------------------------------
🔹 /api/employees/departments/  → Department CRUD (Admin only)
🔹 /api/employees/employees/    → Employee CRUD (Admin/Manager only)
-------------------------------------------------------------
Each ViewSet supports standard REST actions:
  - GET (list, retrieve)
  - POST (create)
  - PUT/PATCH (update)
  - DELETE (soft delete / deactivate for departments)
  - Custom routes:
      - /employees/team/<manager_emp_id>/
      - /employees/team/<manager_emp_id>/overview/
"""

# -----------------------------------------------------------
# 🔹 DRF Router Setup
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")

# -----------------------------------------------------------
# 🔹 URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    path("", include(router.urls)),
]
