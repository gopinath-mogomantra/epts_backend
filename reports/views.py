# ===============================================
# reports/views.py (Final — Production Optimized, Frontend & API Validation Ready)
# ===============================================
# Handles:
# - Weekly Consolidated Report
# - Monthly Consolidated Report
# - Manager-Wise Report
# - Department-Wise Report
# - Employee Performance History
# - CSV Export
# - Print Report (PDF Export)
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
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

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
# ✅ 3. MANAGER-WISE REPORT
# ===========================================================
class ManagerReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Return weekly performance report for employees under a manager."""
        manager_name = request.query_params.get("manager_name")
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        if not manager_name:
            return Response({"error": "Please provide manager_name."}, status=status.HTTP_400_BAD_REQUEST)

        employees = Employee.objects.filter(manager__user__first_name__iexact=manager_name)
        qs = PerformanceEvaluation.objects.filter(
            employee__in=employees, week_number=week, year=year
        ).select_related("employee__user", "department")

        if not qs.exists():
            return Response(
                {"message": f"No data found for manager {manager_name} in Week {week}, {year}."},
                status=status.HTTP_200_OK,
            )

        ranked = qs.annotate(computed_rank=Window(expression=Rank(), order_by=F("total_score").desc()))
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
            {"evaluation_period": f"Week {week}, {year}", "records": ManagerReportSerializer(data, many=True).data},
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
# ✅ 7. PRINT PERFORMANCE REPORT (PDF Export)
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

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setTitle(f"Performance Report - {emp_id}")

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(180, 800, "Employee Performance Report")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, 770, f"Employee ID: {employee.user.emp_id}")
        pdf.drawString(50, 755, f"Name: {employee.user.first_name} {employee.user.last_name}")
        pdf.drawString(50, 740, f"Department: {employee.department.name if employee.department else 'N/A'}")
        if week:
            pdf.drawString(50, 725, f"Week: {week}")
        pdf.drawString(50, 710, f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")

        y = 680
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, "Evaluation Type")
        pdf.drawString(200, y, "Average Score")
        pdf.drawString(350, y, "Remarks")
        pdf.line(45, y - 5, 550, y - 5)

        pdf.setFont("Helvetica", 11)
        y -= 20
        for eval_obj in evaluations:
            avg_score = round(sum(eval_obj.metrics_breakdown.values()) / len(eval_obj.metrics_breakdown), 2)
            pdf.drawString(50, y, eval_obj.evaluation_type)
            pdf.drawString(200, y, str(avg_score))
            pdf.drawString(350, y, (eval_obj.remarks or "")[:60])
            y -= 20
            if y < 80:
                pdf.showPage()
                y = 800

        pdf.showPage()
        pdf.save()

        buffer.seek(0)
        filename = f"Performance_Report_{emp_id}_{timezone.now().strftime('%Y%m%d')}.pdf"
        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
        return response



# ===========================================================
# ✅ 7. PRINT PERFORMANCE REPORT (PDF Export)
# ===========================================================
from reports.utils.pdf_generator import generate_employee_performance_pdf

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

        # ✅ Generate and return the PDF using the utility
        return generate_employee_performance_pdf(employee, evaluations, week)
