# ===========================================================
# performance/views_reports.py ✅ Reports + Export Endpoints
# ===========================================================
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils import timezone

from .models import PerformanceEvaluation
from employee.models import Employee, Department
from .serializers import PerformanceEvaluationSerializer
from .utils_export import generate_excel_report, generate_pdf_report


# ===========================================================
# ✅ Weekly / Department / Manager Report
# ===========================================================
class PerformanceReportView(generics.ListAPIView):
    serializer_class = PerformanceEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = PerformanceEvaluation.objects.select_related(
            "employee__user", "department", "employee__manager__user"
        )

        filter_type = self.request.query_params.get("filter", "weekly").lower()
        value = self.request.query_params.get("value", None)

        if user.role == "Manager":
            qs = qs.filter(employee__manager__user=user)
        elif user.role == "Employee":
            qs = qs.filter(employee__user=user)

        if filter_type == "weekly" and value:
            qs = qs.filter(week_number=value)
        elif filter_type == "department" and value:
            qs = qs.filter(department__code__iexact=value)
        elif filter_type == "manager" and value:
            qs = qs.filter(employee__manager__user__emp_id__iexact=value)

        return qs.order_by("-year", "-week_number")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "count": len(serializer.data),
            "results": serializer.data
        })


# ===========================================================
# ✅ Excel Export (All or Filtered)
# ===========================================================
class PerformanceExcelExportView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = PerformanceEvaluation.objects.select_related("employee__user", "department")
        filter_type = request.query_params.get("filter")
        value = request.query_params.get("value")

        if filter_type == "department" and value:
            qs = qs.filter(department__code__iexact=value)
        elif filter_type == "manager" and value:
            qs = qs.filter(employee__manager__user__emp_id__iexact=value)
        elif filter_type == "week" and value:
            qs = qs.filter(week_number=value)

        filename = f"performance_report_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        return generate_excel_report(qs, filename)
    

# ===========================================================
# ✅ Individual PDF Report (Employee)
# ===========================================================
class EmployeePerformancePDFView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        employee = get_object_or_404(Employee, user__emp_id__iexact=emp_id)
        evaluations = PerformanceEvaluation.objects.filter(employee=employee).order_by("-year", "-week_number")
        return generate_pdf_report(employee, evaluations)
