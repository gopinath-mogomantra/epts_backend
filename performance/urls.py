# ===============================================
# performance/urls.py
# ===============================================
# URL routes for Performance Evaluation Module.
# Includes CRUD, summary, and employee dashboard APIs.
# ===============================================

from django.urls import path
from .views import (
    PerformanceListCreateView,
    PerformanceDetailView,
    PerformanceSummaryView,
    EmployeeDashboardView,
)

app_name = "performance"

urlpatterns = [
    # ------------------------------------------------------
    # PERFORMANCE MANAGEMENT (Admin / Manager)
    # ------------------------------------------------------
    path("", PerformanceListCreateView.as_view(), name="performance-list-create"),
    path("<int:pk>/", PerformanceDetailView.as_view(), name="performance-detail"),

    # ------------------------------------------------------
    # PERFORMANCE SUMMARY (Top / Weak Performers)
    # ------------------------------------------------------
    path("summary/", PerformanceSummaryView.as_view(), name="performance-summary"),

    # ------------------------------------------------------
    # EMPLOYEE DASHBOARD (Self Performance View)
    # ------------------------------------------------------
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee-dashboard"),
]

