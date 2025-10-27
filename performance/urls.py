# ===============================================
# performance/urls.py (Final Verified — Frontend & API Ready)
# ===============================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PerformanceEvaluationViewSet,
    EmployeePerformanceByIdView,  # ✅ Added
    PerformanceSummaryView,
    EmployeeDashboardView,
    EmployeePerformanceView,
)

app_name = "performance"

"""
Routes for Performance Management:
-----------------------------------
🔹 /api/performance/evaluations/           → CRUD operations
🔹 /api/performance/evaluations/<emp_id>/  → Get all evaluations for a specific employee
🔹 /api/performance/summary/               → Weekly + Department summary
🔹 /api/performance/dashboard/             → Employee self-performance dashboard
🔹 /api/performance/employee/<emp_id>/     → Admin/Manager detailed employee view
"""

# -----------------------------------------------------------
# 🔹 DRF Router for PerformanceEvaluation CRUD
# -----------------------------------------------------------
router = DefaultRouter()
router.register(
    r"evaluations",
    PerformanceEvaluationViewSet,
    basename="performance-evaluation"
)

# -----------------------------------------------------------
# 🔹 URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    # ⚠️ Custom route for employee performance (must be above router include)
    path("evaluations/<str:emp_id>/", EmployeePerformanceByIdView.as_view(), name="employee-performance-by-id"),

    path("", include(router.urls)),
    path("summary/", PerformanceSummaryView.as_view(), name="performance-summary"),
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee-dashboard"),
    path("employee/<str:emp_id>/", EmployeePerformanceView.as_view(), name="employee-performance"),
]
