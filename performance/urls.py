# ===============================================
# performance/urls.py (Final Verified — Frontend & API Ready)
# ===============================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PerformanceEvaluationViewSet,
    PerformanceSummaryView,
    EmployeeDashboardView,
    EmployeePerformanceView,
)

app_name = "performance"

"""
Routes for Performance Management:
-----------------------------------
🔹 /api/performance/evaluations/         → CRUD operations
🔹 /api/performance/summary/             → Weekly + Department summary
🔹 /api/performance/dashboard/           → Employee self-performance dashboard
🔹 /api/performance/employee/<emp_id>/   → Individual performance history
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
    path("", include(router.urls)),

    # Custom endpoints (non-ViewSet routes)
    path("summary/", PerformanceSummaryView.as_view(), name="performance-summary"),
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee-dashboard"),
    path("employee/<str:emp_id>/", EmployeePerformanceView.as_view(), name="employee-performance"),
]
