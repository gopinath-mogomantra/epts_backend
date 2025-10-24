# ===============================================
# performance/urls.py (Final Verified Version)
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
- CRUD for evaluations
- Weekly summaries
- Employee dashboards
- Individual performance details
"""

# -----------------------------------------------------------
# DRF Router for PerformanceEvaluation CRUD operations
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r"evaluations", PerformanceEvaluationViewSet, basename="performance-evaluation")

# -----------------------------------------------------------
# Additional custom views (not covered by ViewSet)
# -----------------------------------------------------------
urlpatterns = [
    path("", include(router.urls)),
    path("summary/", PerformanceSummaryView.as_view(), name="performance-summary"),
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee-dashboard"),
    path("employee/<str:emp_id>/", EmployeePerformanceView.as_view(), name="employee-performance"),
]
