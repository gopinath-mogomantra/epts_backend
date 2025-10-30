# ===========================================================
# performance/urls.py ✅ Correctly mapped
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PerformanceEvaluationViewSet,
    EmployeePerformanceByIdView,
    PerformanceSummaryView,
    EmployeeDashboardView,
    EmployeePerformanceView,
    PerformanceDashboardView,  # ← Org-level
)

router = DefaultRouter()
router.register(r"evaluations", PerformanceEvaluationViewSet, basename="performance")

urlpatterns = [
    path("", include(router.urls)),

    # Admin/Manager summary
    path("summary/", PerformanceSummaryView.as_view(), name="performance_summary"),

    # ✅ Organization-level dashboard (Admin / Manager)
    path("dashboard/organization/", PerformanceDashboardView.as_view(), name="performance_dashboard"),

    # ✅ Employee self dashboard
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee_dashboard"),

    # Individual employee by ID
    path("employee/<str:emp_id>/", EmployeePerformanceView.as_view(), name="employee_performance_view"),

    # Employee performance by ID (alternate)
    path("evaluations/<str:emp_id>/", EmployeePerformanceByIdView.as_view(), name="performance_by_emp"),
]
