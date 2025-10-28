# ===========================================================
# reports/urls.py ✅ (Frontend-Aligned & Production-Ready)
# Employee Performance Tracking System (EPTS)
# ===========================================================

from django.urls import path
from .views import (
    WeeklyReportView,
    MonthlyReportView,
    ManagerReportView,
    DepartmentReportView,
    EmployeeHistoryView,
    ExportWeeklyCSVView,
    PrintPerformanceReportView,
)

# -----------------------------------------------------------
# 🌐 App Namespace
# -----------------------------------------------------------
app_name = "reports"

# -----------------------------------------------------------
# 📘 ROUTE SUMMARY
# -----------------------------------------------------------
"""
Reporting & Analytics Endpoints:
-------------------------------------------------------------
🔹 /api/reports/weekly/                     → Weekly consolidated report
🔹 /api/reports/monthly/                    → Monthly consolidated report
🔹 /api/reports/manager/                    → Manager-wise weekly report
🔹 /api/reports/department/                 → Department-wise weekly report
🔹 /api/reports/employee/<emp_id>/history/  → Employee performance trend
🔹 /api/reports/export/weekly-csv/          → Weekly CSV export
🔹 /api/reports/print/<emp_id>/             → PDF export for performance report
-------------------------------------------------------------
All routes are authenticated & role-based (Admin/Manager).
"""

# -----------------------------------------------------------
# 🚀 URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    # 🔹 1️⃣ Weekly Consolidated Report
    # Example: /api/reports/weekly/?week=43&year=2025
    path("weekly/", WeeklyReportView.as_view(), name="weekly_report"),

    # 🔹 2️⃣ Monthly Consolidated Report
    # Example: /api/reports/monthly/?month=10&year=2025
    path("monthly/", MonthlyReportView.as_view(), name="monthly_report"),

    # 🔹 3️⃣ Manager-Wise Weekly Report
    # Example: /api/reports/manager/?manager_name=Ravi&week=43&year=2025
    path("manager/", ManagerReportView.as_view(), name="manager_report"),

    # 🔹 4️⃣ Department-Wise Weekly Report
    # Example: /api/reports/department/?department_name=QA&week=43&year=2025
    path("department/", DepartmentReportView.as_view(), name="department_report"),

    # 🔹 5️⃣ Employee Performance History (Trend)
    # Example: /api/reports/employee/EMP3005/history/
    path(
        "employee/<str:emp_id>/history/",
        EmployeeHistoryView.as_view(),
        name="employee_history",
    ),

    # 🔹 6️⃣ Export Weekly Report as CSV
    # Example: /api/reports/export/weekly-csv/?week=43&year=2025
    path(
        "export/weekly-csv/",
        ExportWeeklyCSVView.as_view(),
        name="export_weekly_csv",
    ),

    # 🔹 7️⃣ Print Performance Report (PDF Export)
    # Example: /api/reports/print/EMP3005/?week=2025-W43
    path(
        "print/<str:emp_id>/",
        PrintPerformanceReportView.as_view(),
        name="report_print",
    ),
]
