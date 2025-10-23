# ===============================================
# reports/urls.py (Final Updated Version)
# ===============================================
# Routes for:
# 1️⃣ Weekly consolidated report
# 2️⃣ Monthly consolidated report
# 3️⃣ Manager-wise weekly report
# 4️⃣ Department-wise weekly report
# 5️⃣ Employee performance history
# 6️⃣ Weekly CSV export
# ===============================================

from django.urls import path
from .views import (
    WeeklyReportView,
    MonthlyReportView,
    ManagerReportView,
    DepartmentReportView,
    EmployeeHistoryView,
    ExportWeeklyCSVView,
)

app_name = "reports"

urlpatterns = [
    # ----------------------------------------------------
    # 1️⃣ Weekly Consolidated Report
    # Example: /api/reports/weekly/?week=43&year=2025
    # ----------------------------------------------------
    path("weekly/", WeeklyReportView.as_view(), name="weekly-report"),

    # ----------------------------------------------------
    # 2️⃣ Monthly Consolidated Report
    # Example: /api/reports/monthly/?month=10&year=2025
    # ----------------------------------------------------
    path("monthly/", MonthlyReportView.as_view(), name="monthly-report"),

    # ----------------------------------------------------
    # 3️⃣ Manager-Wise Weekly Report
    # Example: /api/reports/manager/?manager_name=Ravi Verma&week=43&year=2025
    # ----------------------------------------------------
    path("manager/", ManagerReportView.as_view(), name="manager-report"),

    # ----------------------------------------------------
    # 4️⃣ Department-Wise Weekly Report
    # Example: /api/reports/department/?department_name=IT&week=43&year=2025
    # ----------------------------------------------------
    path("department/", DepartmentReportView.as_view(), name="department-report"),

    # ----------------------------------------------------
    # 5️⃣ Employee Performance History (Trend)
    # Example: /api/reports/employee/EMP3005/history/
    # ----------------------------------------------------
    path(
        "employee/<str:emp_id>/history/",
        EmployeeHistoryView.as_view(),
        name="employee-history",
    ),

    # ----------------------------------------------------
    # 6️⃣ Export Weekly Report as CSV
    # Example: /api/reports/export/weekly-csv/?week=43&year=2025
    # ----------------------------------------------------
    path("export/weekly-csv/", ExportWeeklyCSVView.as_view(), name="export-weekly-csv"),
]
