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

# ✅ App namespace for reverse lookups
app_name = "performance"

urlpatterns = [
    # ------------------------------------------------------
    # 🧾 PERFORMANCE MANAGEMENT (Admin / Manager)
    # ------------------------------------------------------
    # GET:  /api/performance/           → List all evaluations
    # POST: /api/performance/           → Create new evaluation
    path("", PerformanceListCreateView.as_view(), name="performance-list-create"),

    # GET:  /api/performance/<id>/      → Get single evaluation record
    path("<int:pk>/", PerformanceDetailView.as_view(), name="performance-detail"),

    # ------------------------------------------------------
    # 📊 PERFORMANCE SUMMARY (Top / Weak Performers)
    # ------------------------------------------------------
    # GET:  /api/performance/summary/   → Get Top 3 & Weak 3 performers
    path("summary/", PerformanceSummaryView.as_view(), name="performance-summary"),

    # ------------------------------------------------------
    # 🧍‍♂️ EMPLOYEE DASHBOARD (Self Performance View)
    # ------------------------------------------------------
    # GET:  /api/performance/dashboard/ → Get logged-in employee’s evaluations
    path("dashboard/", EmployeeDashboardView.as_view(), name="employee-dashboard"),
]
