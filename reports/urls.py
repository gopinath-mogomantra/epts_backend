# ===============================================
# reports/urls.py
# ===============================================
# Routes for:
# 1. Weekly consolidated report
# 2. Monthly consolidated report
# 3. Employee performance history
# 4. Weekly CSV export
# 5. (Optional) Cached & Combined Reports for Admin use
# ===============================================

from django.urls import path
from .views import (
    WeeklyReportView,
    MonthlyReportView,
    EmployeeHistoryView,
    ExportWeeklyCSVView,
)

app_name = "reports"

urlpatterns = [
    # ----------------------------------------------------
    # 1️⃣ Weekly Consolidated Report
    # Example: /api/reports/weekly/?week=41&year=2025
    # ----------------------------------------------------
    path("weekly/", WeeklyReportView.as_view(), name="weekly-report"),

    # ----------------------------------------------------
    # 2️⃣ Monthly Consolidated Report
    # Example: /api/reports/monthly/?month=10&year=2025
    # ----------------------------------------------------
    path("monthly/", MonthlyReportView.as_view(), name="monthly-report"),

    # ----------------------------------------------------
    # 3️⃣ Employee Performance History (Trend)
    # Example: /api/reports/employee/EMP001/history/
    # ----------------------------------------------------
    path(
        "employee/<str:emp_id>/history/",
        EmployeeHistoryView.as_view(),
        name="employee-history",
    ),

    # ----------------------------------------------------
    # 4️⃣ Export Weekly Report as CSV
    # Example: /api/reports/export/weekly-csv/?week=41&year=2025
    # ----------------------------------------------------
    path("export/weekly-csv/", ExportWeeklyCSVView.as_view(), name="export-weekly-csv"),
]

# ================================================================
# 🔁 Future Extensions (for reference)
# ================================================================
# from .views import CachedReportListView, CombinedReportView
# urlpatterns += [
#     path("cached/", CachedReportListView.as_view(), name="cached-report-list"),
#     path("combined/", CombinedReportView.as_view(), name="combined-report"),
# ]
