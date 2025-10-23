from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PerformanceEvaluationViewSet,
    PerformanceSummaryView,
    EmployeeDashboardView,
    EmployeePerformanceView,
)

router = DefaultRouter()
router.register(r"evaluations", PerformanceEvaluationViewSet, basename="performance-evaluation")

urlpatterns = [
    path("", include(router.urls)),
    path("summary/", PerformanceSummaryView.as_view(), name="performance-summary"),
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee-dashboard"),
    path("employee/<str:emp_id>/", EmployeePerformanceView.as_view(), name="employee-performance"),
]
