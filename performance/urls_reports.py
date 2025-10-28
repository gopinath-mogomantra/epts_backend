# ===========================================================
# performance/urls_reports.py ✅ Final URL Configuration
# ===========================================================
from django.urls import path
from .views_reports import (
    PerformanceReportView,
    PerformanceExcelExportView,
    EmployeePerformancePDFView,
)

app_name = "performance-reports"

urlpatterns = [
    path("reports/", PerformanceReportView.as_view(), name="performance-report"),
    path("reports/export-excel/", PerformanceExcelExportView.as_view(), name="export-excel"),
    path("reports/<str:emp_id>/export-pdf/", EmployeePerformancePDFView.as_view(), name="export-pdf"),
]
