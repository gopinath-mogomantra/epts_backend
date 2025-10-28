# ===========================================================
# performance/urls.py ✅ (Frontend-Aligned & Production-Ready)
# Employee Performance Tracking System (EPTS)
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PerformanceEvaluationViewSet,
    EmployeePerformanceByIdView,
    PerformanceSummaryView,
    EmployeeDashboardView,
    EmployeePerformanceView,
)

# -----------------------------------------------------------
# 🌐 App Namespace
# -----------------------------------------------------------
app_name = "performance"

# -----------------------------------------------------------
# 📘 ROUTE SUMMARY
# -----------------------------------------------------------
"""
Performance Management Endpoints:
-------------------------------------------------------------
🔹 /api/performance/evaluations/             → CRUD (Admin/Manager)
🔹 /api/performance/evaluations/<emp_id>/    → List employee evaluations
🔹 /api/performance/summary/                 → Weekly + Department summary
🔹 /api/performance/dashboard/               → Employee’s personal dashboard
🔹 /api/performance/employee/<emp_id>/       → Admin/Manager detailed view
-------------------------------------------------------------
Each route is authenticated and role-restricted using DRF permissions.
"""

# -----------------------------------------------------------
# 🚀 DRF Router Configuration
# -----------------------------------------------------------
router = DefaultRouter()
router.register(
    r"evaluations",
    PerformanceEvaluationViewSet,
    basename="performance-evaluation",
)

# -----------------------------------------------------------
# 🛠️ URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    # 🔹 Custom Employee-Specific Evaluations
    path(
        "evaluations/<str:emp_id>/",
        EmployeePerformanceByIdView.as_view(),
        name="employee_performance_by_id",
    ),

    # 🔹 Auto-registered CRUD routes
    path("", include(router.urls)),

    # 🔹 Performance Summary & Analytics
    path("summary/", PerformanceSummaryView.as_view(), name="performance_summary"),

    # 🔹 Employee Dashboard & Individual Performance
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee_dashboard"),
    path("employee/<str:emp_id>/", EmployeePerformanceView.as_view(), name="employee_performance"),
]
