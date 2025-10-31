# ===============================================
# reports/views.py (Final — Production Optimized & Frontend Ready)
# ===============================================
# Handles:
# - Weekly Consolidated Report
# - Monthly Consolidated Report
# - Manager-Wise Report
# - Department-Wise Report
# - Employee Performance History
# - CSV Export
# - PDF Export (Print Performance Report)
# ===============================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Avg, F, Q, Window
from django.db.models.functions import Rank
from django.utils import timezone
from django.http import HttpResponse
from datetime import timedelta, datetime
from itertools import chain
import csv
import logging

from employee.models import Employee
from performance.models import PerformanceEvaluation
from feedback.models import GeneralFeedback, ManagerFeedback, ClientFeedback
from .models import CachedReport
from .serializers import (
    WeeklyReportSerializer,
    MonthlyReportSerializer,
    EmployeeHistorySerializer,
    ManagerReportSerializer,
    DepartmentReportSerializer,
)

from reports.utils.pdf_generator import generate_employee_performance_pdf

logger = logging.getLogger(__name__)


# ===========================================================
# 🧠 Helper: Compute Feedback Average
# ===========================================================
def get_feedback_average(employee, start_date=None, end_date=None):
    """Compute average rating across all feedback sources for a given employee."""
    filters = Q(employee=employee)
    if start_date and end_date:
        filters &= Q(created_at__range=(start_date, end_date))

    ratings = list(chain(
        GeneralFeedback.objects.filter(filters).values_list("rating", flat=True),
        ManagerFeedback.objects.filter(filters).values_list("rating", flat=True),
        ClientFeedback.objects.filter(filters).values_list("rating", flat=True),
    ))

    return round(sum(ratings) / len(ratings), 2) if ratings else 0.0


# ===========================================================
# ✅ 1. WEEKLY CONSOLIDATED REPORT
# ===========================================================
class WeeklyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return consolidated weekly performance summary."""
        try:
            week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
            year = int(request.query_params.get("year", timezone.now().year))
            save_cache = request.query_params.get("save_cache", "false").lower() == "true"

            qs = (
                PerformanceEvaluation.objects.filter(week_number=week, year=year)
                .select_related("employee__user", "department")
                .annotate(emp_id=F("employee__user__emp_id"))
            )

            if not qs.exists():
                return Response(
                    {"message": f"No performance data found for Week {week}, {year}."},
                    status=status.HTTP_200_OK,
                )

            feedback_map = {
                emp.id: get_feedback_average(emp)
                for emp in Employee.objects.filter(id__in=qs.values_list("employee_id", flat=True))
            }

            ranked = qs.annotate(
                computed_rank=Window(expression=Rank(), order_by=F("total_score").desc())
            )

            result = [
                {
                    "emp_id": p.employee.user.emp_id,
                    "employee_full_name": f"{p.employee.user.first_name} {p.employee.user.last_name}".strip(),
                    "department": p.department.name if p.department else "-",
                    "total_score": float(p.total_score),
                    "average_score": float(p.average_score),
                    "feedback_avg": feedback_map.get(p.employee.id, 0.0),
                    "week_number": week,
                    "year": year,
                    "rank": int(p.computed_rank),
                    "remarks": p.remarks or "",
                }
                for p in ranked
            ]

            if save_cache:
                CachedReport.objects.update_or_create(
                    report_type="weekly",
                    year=year,
                    week_number=week,
                    defaults={
                        "payload": {"records": result},
                        "generated_by": request.user,
                    },
                )

            return Response(
                {
                    "evaluation_period": f"Week {week}, {year}",
                    "total_records": len(result),
                    "records": WeeklyReportSerializer(result, many=True).data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception("❌ WeeklyReport Error: %s", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================
# ✅ 2. MONTHLY CONSOLIDATED REPORT
# ===========================================================
class MonthlyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return monthly average performance summary."""
        try:
            month = int(request.query_params.get("month", timezone.now().month))
            year = int(request.query_params.get("year", timezone.now().year))
            save_cache = request.query_params.get("save_cache", "false").lower() == "true"

            qs = PerformanceEvaluation.objects.filter(
                review_date__month=month, year=year
            ).select_related("employee__user", "department")

            if not qs.exists():
                return Response(
                    {"message": f"No performance data found for {month}/{year}."},
                    status=status.HTTP_200_OK,
                )

            data = []
            employees = Employee.objects.filter(id__in=qs.values_list("employee_id", flat=True))

            for emp in employees.select_related("user", "department"):
                emp_qs = qs.filter(employee=emp)
                if not emp_qs.exists():
                    continue

                avg_score = round(emp_qs.aggregate(avg=Avg("average_score"))["avg"], 2)
                best_week_obj = emp_qs.order_by("-average_score").first()

                fb_avg = get_feedback_average(
                    emp,
                    start_date=best_week_obj.created_at - timedelta(days=30),
                    end_date=best_week_obj.created_at,
                )

                data.append({
                    "emp_id": emp.user.emp_id,
                    "employee_full_name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                    "department": emp.department.name if emp.department else "-",
                    "month": month,
                    "year": year,
                    "avg_score": avg_score,
                    "feedback_avg": fb_avg,
                    "best_week": best_week_obj.week_number,
                    "best_week_score": best_week_obj.average_score,
                })

            if save_cache:
                CachedReport.objects.update_or_create(
                    report_type="monthly",
                    year=year,
                    month=month,
                    defaults={
                        "payload": {"records": data},
                        "generated_by": request.user,
                    },
                )

            return Response(
                {
                    "evaluation_period": f"Month {month}, {year}",
                    "total_records": len(data),
                    "records": MonthlyReportSerializer(data, many=True).data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception("❌ MonthlyReport Error: %s", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================
# ✅ 3. MANAGER-WISE REPORT (Fixed — Uses Evaluator Relation)
# ===========================================================
class ManagerReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return weekly performance report for employees evaluated by a specific manager."""
        manager_name = request.query_params.get("manager_name")
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        if not manager_name:
            return Response({"error": "Please provide manager_name."}, status=status.HTTP_400_BAD_REQUEST)

        # Split name into first and last name for matching
        parts = manager_name.split()
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        # ✅ Find manager by name and ensure they exist
        manager = (
            Employee.objects.filter(
                user__first_name__iexact=first_name,
                user__last_name__iexact=last_name,
                user__role="Manager"
            )
            .select_related("user")
            .first()
        )

        if not manager:
            return Response(
                {"error": f"Manager '{manager_name}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ✅ Use evaluator = manager.user (correct foreign key)
        qs = PerformanceEvaluation.objects.filter(
            evaluator=manager.user,
            week_number=week,
            year=year
        ).select_related("employee__user", "department")

        if not qs.exists():
            return Response(
                {"message": f"No data found for manager {manager_name} in Week {week}, {year}."},
                status=status.HTTP_200_OK,
            )

        # Rank employees by total_score within manager’s team
        ranked = qs.annotate(
            computed_rank=Window(expression=Rank(), order_by=F("total_score").desc())
        )

        # Build response data
        data = [
            {
                "manager_full_name": manager_name,
                "emp_id": p.employee.user.emp_id,
                "employee_full_name": f"{p.employee.user.first_name} {p.employee.user.last_name}".strip(),
                "department": p.department.name if p.department else "-",
                "total_score": float(p.total_score),
                "average_score": float(p.average_score),
                "feedback_avg": get_feedback_average(p.employee),
                "week_number": week,
                "year": year,
                "rank": int(p.computed_rank),
                "remarks": p.remarks or "",
            }
            for p in ranked
        ]

        return Response(
            {
                "manager_name": manager_name,
                "evaluation_period": f"Week {week}, {year}",
                "total_employees": len(data),
                "records": ManagerReportSerializer(data, many=True).data,
            },
            status=status.HTTP_200_OK,
        )
# ===========================================================
# ✅ 4. DEPARTMENT-WISE REPORT
# ===========================================================
class DepartmentReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return weekly performance report for a department."""
        dept_name = request.query_params.get("department_name")
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        if not dept_name:
            return Response({"error": "Please provide department_name."}, status=status.HTTP_400_BAD_REQUEST)

        employees = Employee.objects.filter(department__name__iexact=dept_name)
        qs = (
            PerformanceEvaluation.objects.filter(employee__in=employees, week_number=week, year=year)
            .select_related("employee__user", "employee__manager__user", "department")
            .annotate(computed_rank=Window(expression=Rank(), order_by=F("total_score").desc()))
        )

        if not qs.exists():
            return Response(
                {"message": f"No data found for department {dept_name} in Week {week}, {year}."},
                status=status.HTTP_200_OK,
            )

        data = []
        for p in qs:
            emp = p.employee
            if emp.manager and hasattr(emp.manager, "user"):
                manager_full = f"{emp.manager.user.first_name} {emp.manager.user.last_name}".strip()
            else:
                manager_full = "Not Assigned"

            data.append({
                "department_name": dept_name,
                "emp_id": emp.user.emp_id,
                "employee_full_name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                "manager_full_name": manager_full,
                "total_score": float(p.total_score),
                "average_score": float(p.average_score),
                "feedback_avg": get_feedback_average(emp),
                "week_number": week,
                "year": year,
                "rank": int(p.computed_rank),
                "remarks": p.remarks or "",
            })

        return Response(
            {"evaluation_period": f"Week {week}, {year}", "records": DepartmentReportSerializer(data, many=True).data},
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ✅ 5. EMPLOYEE PERFORMANCE HISTORY
# ===========================================================
class EmployeeHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        """Return weekly trend history for a specific employee."""
        try:
            employee = Employee.objects.select_related("user").get(user__emp_id=emp_id)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        qs = PerformanceEvaluation.objects.filter(employee=employee).order_by("year", "week_number")
        if not qs.exists():
            return Response({"message": "No performance history found."}, status=status.HTTP_200_OK)

        result = [
            {
                "week_number": p.week_number,
                "year": p.year,
                "average_score": float(p.average_score),
                "feedback_avg": get_feedback_average(employee, start_date=p.created_at - timedelta(days=7), end_date=p.created_at),
                "remarks": p.remarks or "",
                "rank": p.rank,
            }
            for p in qs
        ]

        return Response(
            {"employee": employee.user.emp_id, "records": EmployeeHistorySerializer(result, many=True).data},
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ✅ 6. EXPORT WEEKLY REPORT AS CSV
# ===========================================================
class ExportWeeklyCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Export weekly report as a downloadable CSV file."""
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        qs = PerformanceEvaluation.objects.filter(week_number=week, year=year).select_related("employee__user", "department")

        if not qs.exists():
            return Response({"message": "No data found for CSV export."}, status=status.HTTP_200_OK)

        filename = f"Weekly_Report_Week{week}_{year}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(["Emp ID", "Employee Name", "Department", "Total Score", "Average Score", "Rank"])

        for p in qs.order_by("-total_score"):
            writer.writerow([
                p.employee.user.emp_id,
                f"{p.employee.user.first_name} {p.employee.user.last_name}".strip(),
                p.department.name if p.department else "-",
                round(float(p.total_score), 2),
                round(float(p.average_score), 2),
                p.rank or "-",
            ])

        return response
    


# ===========================================================
# ✅ 7. EXPORT WEEKLY REPORT AS EXCEL (.xlsx)
# ===========================================================
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

class ExportWeeklyExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Export weekly report as downloadable Excel file (.xlsx)."""
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        qs = (
            PerformanceEvaluation.objects.filter(week_number=week, year=year)
            .select_related("employee__user", "department")
            .order_by("-total_score")
        )

        if not qs.exists():
            return Response(
                {"message": f"No performance data found for Week {week}, {year}."},
                status=status.HTTP_200_OK,
            )

        # Create Excel Workbook and Sheet
        wb = Workbook()
        ws = wb.active
        ws.title = f"Week {week} Report"

        # Define Header Style
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin")
        )

        # Header Row
        headers = [
            "Emp ID", "Employee Name", "Department",
            "Total Score", "Average Score", "Feedback Avg", "Rank", "Remarks"
        ]
        ws.append(headers)
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        # Data Rows
        for idx, p in enumerate(qs, start=2):
            emp = p.employee
            fb_avg = get_feedback_average(emp)

            ws.append([
                emp.user.emp_id,
                f"{emp.user.first_name} {emp.user.last_name}".strip(),
                p.department.name if p.department else "-",
                round(float(p.total_score), 2),
                round(float(p.average_score), 2),
                fb_avg,
                p.rank or "-",
                p.remarks or "",
            ])

        # Apply Borders and Alignment to All Cells
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center", vertical="center")

        # Auto-adjust column width
        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 4

        # Generate Filename and Response
        filename = f"Weekly_Report_Week{week}_{year}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)

        logger.info(f"📊 Excel report generated for Week {week}, {year} by {request.user.emp_id}")
        return response



# ===========================================================
# ✅ 8. PRINT PERFORMANCE REPORT (PDF Export via Utility)
# ===========================================================
class PrintPerformanceReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        """Generate printable PDF performance report for employee."""
        week = request.query_params.get("week")

        try:
            employee = Employee.objects.select_related("user", "department").get(user__emp_id__iexact=emp_id)
        except Employee.DoesNotExist:
            return Response({"error": f"Employee '{emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        # Role-based access
        user = request.user
        role = getattr(user, "role", "")
        if role == "Employee" and user.emp_id != emp_id:
            return Response({"error": "Employees can only print their own reports."}, status=status.HTTP_403_FORBIDDEN)
        if role == "Manager" and not Employee.objects.filter(manager__user=user, user__emp_id=emp_id).exists():
            return Response({"error": "Managers can print only their team reports."}, status=status.HTTP_403_FORBIDDEN)

        evaluations = PerformanceEvaluation.objects.filter(employee__user__emp_id__iexact=emp_id)
        if week:
            evaluations = evaluations.filter(week_number=week.split("-W")[-1])

        if not evaluations.exists():
            return Response({"message": "No performance data found for this employee."}, status=status.HTTP_200_OK)

        # ✅ Generate and return the PDF using the centralized utility
        return generate_employee_performance_pdf(employee, evaluations, week)



# ===========================================================
# ✅ 9. EXPORT MONTHLY REPORT AS EXCEL (.xlsx)
# ===========================================================
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

class ExportMonthlyExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Export monthly consolidated report as Excel (.xlsx)."""
        month = int(request.query_params.get("month", timezone.now().month))
        year = int(request.query_params.get("year", timezone.now().year))

        # Fetch data using same logic as MonthlyReportView
        qs = PerformanceEvaluation.objects.filter(
            review_date__month=month, year=year
        ).select_related("employee__user", "department")

        if not qs.exists():
            return Response(
                {"message": f"No performance data found for {month}/{year}."},
                status=status.HTTP_200_OK,
            )

        employees = Employee.objects.filter(id__in=qs.values_list("employee_id", flat=True))
        wb = Workbook()
        ws = wb.active
        ws.title = f"Month {month} Report"

        # Header styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin")
        )

        # Header row
        headers = [
            "Emp ID", "Employee Name", "Department", "Avg Score",
            "Feedback Avg", "Best Week", "Best Week Score"
        ]
        ws.append(headers)
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        # Data rows
        for idx, emp in enumerate(employees.select_related("user", "department"), start=2):
            emp_qs = qs.filter(employee=emp)
            if not emp_qs.exists():
                continue

            avg_score = round(emp_qs.aggregate(avg=Avg("average_score"))["avg"], 2)
            best_week_obj = emp_qs.order_by("-average_score").first()
            fb_avg = get_feedback_average(
                emp,
                start_date=best_week_obj.created_at - timedelta(days=30),
                end_date=best_week_obj.created_at,
            )

            ws.append([
                emp.user.emp_id,
                f"{emp.user.first_name} {emp.user.last_name}".strip(),
                emp.department.name if emp.department else "-",
                avg_score,
                fb_avg,
                best_week_obj.week_number,
                best_week_obj.average_score,
            ])

        # Borders & alignment
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=len(headers)):
            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center", vertical="center")

        # Auto width
        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 4

        # Generate filename and response
        filename = f"Monthly_Report_{month}_{year}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        wb.save(response)

        logger.info(f"📊 Monthly Excel report generated for {month}/{year} by {request.user.emp_id}")
        return response
