# ===============================================
# reports/views.py (Final — Notification Integrated & Production Ready)
# ===============================================
# Handles:
# - Weekly Consolidated Report
# - Monthly Consolidated Report
# - Manager-Wise Report
# - Department-Wise Report
# - Employee Performance History
# - CSV Export
# - Excel Export (Weekly + Monthly)
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

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

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
    CachedReportSerializer,
)

from reports.utils.pdf_generator import generate_employee_performance_pdf
from notifications.views import create_report_notification  # ✅ notification trigger

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

            # 🔔 Create notification for weekly report generation
            try:
                message = f"Weekly performance report generated for Week {week}, {year}."
                create_report_notification(
                    triggered_by=request.user,
                    report_type="Weekly Report",
                    link=f"/reports/weekly/?week={week}&year={year}",
                    message=message,
                    department=None,
                )
            except Exception as e:
                logger.error(f"⚠️ Weekly report notification failed: {e}")

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

            # 🔔 Create notification for monthly report generation
            try:
                message = f"Monthly performance report generated for {month}/{year}."
                create_report_notification(
                    triggered_by=request.user,
                    report_type="Monthly Report",
                    link=f"/reports/monthly/?month={month}&year={year}",
                    message=message,
                    department=None,
                )
            except Exception as e:
                logger.error(f"⚠️ Monthly report notification failed: {e}")

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
# ✅ 3. DEPARTMENT-WISE WEEKLY REPORT (Final)
# ===========================================================
class DepartmentReportView(APIView):
    """Returns department-wise weekly performance report."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        department_name = request.query_params.get("department_name")
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        if not department_name:
            return Response({"error": "Please provide department_name."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            employees = Employee.objects.filter(department__name__iexact=department_name)
            if not employees.exists():
                return Response({"message": f"No employees found in department {department_name}."}, status=status.HTTP_200_OK)

            qs = PerformanceEvaluation.objects.filter(employee__in=employees, week_number=week, year=year).select_related("employee__user", "department")
            if not qs.exists():
                return Response({"message": f"No performance data found for department {department_name} in Week {week}, {year}."}, status=status.HTTP_200_OK)

            feedback_map = {emp.id: get_feedback_average(emp) for emp in employees}

            ranked = qs.annotate(computed_rank=Window(expression=Rank(), order_by=F("total_score").desc()))

            records = [
                {
                    "department_name": department_name,
                    "emp_id": perf.employee.user.emp_id,
                    "employee_full_name": f"{perf.employee.user.first_name} {perf.employee.user.last_name}".strip(),
                    "total_score": float(perf.total_score),
                    "average_score": float(perf.average_score),
                    "feedback_avg": feedback_map.get(perf.employee.id, 0.0),
                    "rank": int(perf.computed_rank),
                    "remarks": perf.remarks or "",
                }
                for perf in ranked
            ]

            create_report_notification(
                triggered_by=request.user,
                report_type="Department Weekly Report",
                link=f"/reports/department/?department_name={department_name}&week={week}&year={year}",
                message=f"Department-wise report generated for {department_name} (Week {week}, {year}).",
                department=None,
            )

            return Response(
                {"department_name": department_name, "evaluation_period": f"Week {week}, {year}", "total_employees": len(records), "records": records},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception(f"❌ DepartmentReport Error: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================
# ✅ 4. MANAGER REPORT (Placeholder)
# ===========================================================
class ManagerReportView(APIView):
    """Placeholder: Manager-wise weekly report."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {"message": "Manager-wise report endpoint under construction."},
            status=status.HTTP_200_OK,
        )
