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
    ExportWeeklyExcelView,      # ✅ NEW Excel export
    PrintPerformanceReportView,
    ExportMonthlyExcelView,

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
🔹 /api/reports/export/weekly-excel/        → Weekly Excel (.xlsx) export ✅
🔹 /api/reports/print/<emp_id>/             → PDF export for performance report
-------------------------------------------------------------
All routes are authenticated & role-based (Admin/Manager).
"""

# -----------------------------------------------------------
# 🚀 URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    # 🔹 1️⃣ Weekly Consolidated Report
    path("weekly/", WeeklyReportView.as_view(), name="weekly_report"),

    # 🔹 2️⃣ Monthly Consolidated Report
    path("monthly/", MonthlyReportView.as_view(), name="monthly_report"),

    # 🔹 3️⃣ Manager-Wise Weekly Report
    path("manager/", ManagerReportView.as_view(), name="manager_report"),

    # 🔹 4️⃣ Department-Wise Weekly Report
    path("department/", DepartmentReportView.as_view(), name="department_report"),

    # 🔹 5️⃣ Employee Performance History (Trend)
    path(
        "employee/<str:emp_id>/history/",
        EmployeeHistoryView.as_view(),
        name="employee_history",
    ),

    # 🔹 6️⃣ Export Weekly Report as CSV
    path(
        "export/weekly-csv/",
        ExportWeeklyCSVView.as_view(),
        name="export_weekly_csv",
    ),

    # 🔹 7️⃣ Export Weekly Report as Excel (.xlsx) ✅
    path(
        "export/weekly-excel/",
        ExportWeeklyExcelView.as_view(),
        name="export_weekly_excel",
    ),


    # 🔹 8️⃣ Print Performance Report (PDF Export)
    path(
        "print/<str:emp_id>/",
        PrintPerformanceReportView.as_view(),
        name="report_print",
    ),

    # 🔹 8️⃣ Export Monthly Report as Excel
# Example: /api/reports/export/monthly-excel/?month=10&year=2025
path(
    "export/monthly-excel/",
    ExportMonthlyExcelView.as_view(),
    name="export_monthly_excel",
),

]
