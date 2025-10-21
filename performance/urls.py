# ===============================================
# performance/urls.py (Final Polished Version)
# ===============================================
# Routes for Performance Evaluation Module
# Includes CRUD (via Router), Summary (Admin/Manager),
# and Dashboard (Employee) APIs
# ===============================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PerformanceEvaluationViewSet,
    PerformanceSummaryView,
    EmployeeDashboardView,
)

# ✅ App namespace for reverse() and URL resolution
app_name = "performance"

# ------------------------------------------------------
# 🔹 Router Registration for CRUD Endpoints
# ------------------------------------------------------
router = DefaultRouter()
router.register(r"evaluations", PerformanceEvaluationViewSet, basename="performance-evaluation")

urlpatterns = [
    # ------------------------------------------------------
    # ⚙️ CRUD Operations
    # ------------------------------------------------------
    # Admin & Manager: Full access
    # Employee: Read-only access (self records only)
    # Base URLs:
    #   GET/POST   → /api/performance/evaluations/
    #   GET/PUT/DELETE → /api/performance/evaluations/<id>/
    path("", include(router.urls)),

    # ------------------------------------------------------
    # 📊 PERFORMANCE SUMMARY (Top 3 / Weak 3)
    # ------------------------------------------------------
    # GET → /api/performance/summary/
    # Role: Admin / Manager
    path("summary/", PerformanceSummaryView.as_view(), name="performance-summary"),

    # ------------------------------------------------------
    # 🧍‍♂️ EMPLOYEE DASHBOARD (Self Performance)
    # ------------------------------------------------------
    # GET → /api/performance/dashboard/
    # Role: Employee
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee-dashboard"),

    # ------------------------------------------------------
    # 📈 (Optional) Analytics / Department Reports (Future)
    # ------------------------------------------------------
    # Example: /api/performance/department/<dept_id>/summary/
    # path("department/<int:dept_id>/summary/", DepartmentPerformanceSummaryView.as_view()),
]
