# ===============================================
# reports/urls.py
# ===============================================

from django.urls import path
from .views import (
    WeeklyReportView,
    MonthlyReportView,
    DepartmentReportView,
    ManagerReportView,
    ExportWeeklyExcelView,
    ExportMonthlyExcelView,
    PrintPerformanceReportView, 
    CachedReportListView,
    CachedReportDetailView,
    CachedReportArchiveView,
    CachedReportRestoreView,
    CachedReportDeleteView,
)

# Namespace for reverse URL lookups
app_name = "reports"

# ===========================================================
# ROUTE SUMMARY
# ===========================================================
"""
Reporting & Analytics Endpoints (v1):
-------------------------------------------------------------
📊 AGGREGATE REPORTS:
  GET  /weekly/                          → Weekly consolidated report
  GET  /weekly/<start_date>/             → Weekly report for specific date
  GET  /monthly/                         → Monthly consolidated report
  GET  /monthly/<year>/<month>/          → Monthly report for specific period

📈 BREAKDOWN REPORTS:
  GET  /department/                      → Department-wise analysis
  GET  /manager/                         → Manager-wise team summary

📥 EXPORT ENDPOINTS:
  GET  /export/weekly-excel/             → Download weekly Excel (.xlsx)
  GET  /export/monthly-excel/            → Download monthly Excel (.xlsx)
  GET  /export/pdf/<emp_id>/             → Employee-specific PDF report

💾 CACHED REPORTS:
  GET    /cache/                         → List all cached reports
  GET    /cache/<id>/                    → Retrieve specific cached report
  PATCH  /cache/<id>/archive/            → Archive cached report
  PATCH  /cache/<id>/restore/            → Restore archived report
  DELETE /cache/<id>/                    → Permanently delete cached report

-------------------------------------------------------------
🔒 Authentication: All endpoints require Admin/Manager role
📅 Date formats: YYYY-MM-DD for start_date, YYYY for year, MM for month
🔢 emp_id format: String (supports both numeric and alphanumeric IDs)
-------------------------------------------------------------
"""

# ===========================================================
# URL Patterns
# ===========================================================
urlpatterns = [
    # ========== AGGREGATE REPORTS ==========
    path(
        "weekly/",
        WeeklyReportView.as_view(),
        name="weekly_report"
    ),
    path(
        "weekly/<str:start_date>/",
        WeeklyReportView.as_view(),
        name="weekly_report_dated"
    ),
    path(
        "monthly/",
        MonthlyReportView.as_view(),
        name="monthly_report"
    ),
    path(
        "monthly/<int:year>/<int:month>/",
        MonthlyReportView.as_view(),
        name="monthly_report_dated"
    ),

    # ========== BREAKDOWN REPORTS ==========
    path(
        "department/",
        DepartmentReportView.as_view(),
        name="department_report"
    ),
    path(
        "manager/",
        ManagerReportView.as_view(),
        name="manager_report"
    ),

    # ========== EXPORT ENDPOINTS ==========
    path(
        "export/weekly-excel/",
        ExportWeeklyExcelView.as_view(),
        name="export_weekly_excel"
    ),
    path(
        "export/monthly-excel/",
        ExportMonthlyExcelView.as_view(),
        name="export_monthly_excel"
    ),
    path(
        "export/pdf/<str:emp_id>/",
        PrintPerformanceReportView.as_view(),
        name="export_employee_pdf"
    ),

    # ========== CACHED REPORTS ==========
    path(
        "cache/",
        CachedReportListView.as_view(),
        name="cached_reports_list"
    ),
    path(
        "cache/<int:pk>/",
        CachedReportDetailView.as_view(),
        name="cached_report_detail"
    ),
    path(
        "cache/<int:pk>/archive/",
        CachedReportArchiveView.as_view(),
        name="cached_report_archive"
    ),
    path(
        "cache/<int:pk>/restore/",
        CachedReportRestoreView.as_view(),
        name="cached_report_restore"
    ),
    path(
        "cache/<int:pk>/delete/",
        CachedReportDeleteView.as_view(),
        name="cached_report_delete"
    ),
]

# ===========================================================
# URL REFERENCE EXAMPLES
# ===========================================================
"""
Usage in views (reverse lookup):
    from django.urls import reverse
    
    # Basic reports
    weekly_url = reverse('reports:weekly_report')
    monthly_url = reverse('reports:monthly_report')
    
    # Dated reports
    specific_week = reverse('reports:weekly_report_dated', 
                           kwargs={'start_date': '2025-01-06'})
    specific_month = reverse('reports:monthly_report_dated',
                            kwargs={'year': 2025, 'month': 1})
    
    # Employee PDF
    pdf_url = reverse('reports:export_employee_pdf',
                     kwargs={'emp_id': 'EMP001'})
    
    # Cache operations
    cache_list = reverse('reports:cached_reports_list')
    archive_report = reverse('reports:cached_report_archive',
                            kwargs={'pk': 42})

Usage in templates:
    {% url 'reports:weekly_report' %}
    {% url 'reports:export_employee_pdf' emp_id='EMP001' %}
    {% url 'reports:cached_report_archive' pk=report.id %}
"""