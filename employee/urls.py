# ===============================================
# employee/urls.py
# ===============================================

from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import DepartmentViewSet, EmployeeViewSet

# Namespace for reverse lookups
app_name = "employee"

# -----------------------------------------------------------
# DRF DefaultRouter for automatic CRUD routes
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r"departments", DepartmentViewSet, basename="department")
router.register(r"employees", EmployeeViewSet, basename="employee")

urlpatterns = [
    path("", include(router.urls)),
]
