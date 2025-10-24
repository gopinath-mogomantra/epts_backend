# ===============================================
# employee/urls.py (Final Verified Version)
# ===============================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DepartmentViewSet, EmployeeViewSet

app_name = "employee"

"""
Auto-registers all CRUD API endpoints for:
- /api/employees/
- /api/departments/
with full REST functionality (list, retrieve, create, update, delete)
"""

# -----------------------------------------------------------
# DRF DefaultRouter for automatic CRUD routes
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"employees", EmployeeViewSet, basename="employee")

urlpatterns = [
    path("", include(router.urls)),
]
