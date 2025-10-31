# ===========================================================
# reports/urls.py ✅ (Frontend-Aligned & Production-Ready)
# ===========================================================

from django.urls import path
from .views import (
    WeeklyReportView,
    MonthlyReportView,
    DepartmentReportView,
    ManagerReportView,
    ExportWeeklyExcelView,
    ExportMonthlyExcelView,
    CachedReportListView,
    CachedReportArchiveView,
    CachedReportRestoreView,
)

# 🌐 Namespace
app_name = "reports"

# ===========================================================
# 📘 ROUTE SUMMARY
# ===========================================================
"""
Reporting & Analytics Endpoints:
-------------------------------------------------------------
🔹 /api/reports/weekly/                     → Weekly consolidated report
🔹 /api/reports/monthly/                    → Monthly consolidated report
🔹 /api/reports/department/                 → Department-wise weekly report
🔹 /api/reports/manager/                    → Manager-wise weekly report (placeholder)
🔹 /api/reports/export/weekly-excel/        → Weekly Excel export (.xlsx)
🔹 /api/reports/export/monthly-excel/       → Monthly Excel export (.xlsx)
🔹 /api/reports/cache/                      → Cached report listing (Admin/Manager)
🔹 /api/reports/cache/<id>/archive/         → Archive cached report
🔹 /api/reports/cache/<id>/restore/         → Restore cached report
-------------------------------------------------------------
All routes are authenticated (Admin/Manager access).
"""

# ===========================================================
# 🚀 URL Patterns
# ===========================================================
urlpatterns = [
    # 🔹 Weekly & Monthly Reports
    path("weekly/", WeeklyReportView.as_view(), name="weekly_report"),
    path("monthly/", MonthlyReportView.as_view(), name="monthly_report"),

    # 🔹 Department-Wise Report
    path("department/", DepartmentReportView.as_view(), name="department_report"),

    # 🔹 Manager-Wise Report (placeholder)
    path("manager/", ManagerReportView.as_view(), name="manager_report"),

    # 🔹 Excel Exports
    path("export/weekly-excel/", ExportWeeklyExcelView.as_view(), name="export_weekly_excel"),
    path("export/monthly-excel/", ExportMonthlyExcelView.as_view(), name="export_monthly_excel"),

    # 🔹 Cached Reports
    path("cache/", CachedReportListView.as_view(), name="cached_reports_dashboard"),
    path("cache/<int:pk>/archive/", CachedReportArchiveView.as_view(), name="cached_report_archive"),
    path("cache/<int:pk>/restore/", CachedReportRestoreView.as_view(), name="cached_report_restore"),
]
