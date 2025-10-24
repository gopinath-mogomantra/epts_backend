# ===========================================================
# employee/urls.py (Frontend-Aligned & Demo-Ready — 2025-10-24)
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, EmployeeViewSet

app_name = "employee"

"""
Auto-registers all CRUD API endpoints for:
-------------------------------------------------------------
🔹 /api/departments/ → Department CRUD (Admin restricted)
🔹 /api/employees/   → Employee CRUD (Admin/Manager restricted)
-------------------------------------------------------------
Each route automatically supports:
  - GET (list, retrieve)
  - POST (create)
  - PUT/PATCH (update)
  - DELETE (soft delete for departments)
"""

# -----------------------------------------------------------
# DRF Router Setup (Auto CRUD)
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="departments")
router.register(r"employees", EmployeeViewSet, basename="employees")

# -----------------------------------------------------------
# URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    path("", include(router.urls)),
]
