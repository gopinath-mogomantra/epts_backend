# ===============================================
# reports/views.py (Final Production-Stable Version)
# ===============================================
# Handles:
# - Weekly Consolidated Report
# - Monthly Consolidated Report
# - Manager-Wise Report
# - Department-Wise Report
# - Employee Performance History
# - CSV Export
# ===============================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Avg, F, Q, Window
from django.db.models.functions import Rank
from django.utils import timezone
from django.http import HttpResponse
from datetime import timedelta, datetime
import csv
from itertools import chain

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

# ===========================================================
# 🧠 Helper: Compute Feedback Average
# ===========================================================
def get_feedback_average(employee, start_date=None, end_date=None):
    """Compute average rating from all feedback sources for a given employee."""
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
        """Returns weekly performance summary for all employees."""
        try:
            week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
            year = int(request.query_params.get("year", timezone.now().year))
            save_cache = request.query_params.get("save_cache", "false").lower() == "true"

            perf_qs = (
                PerformanceEvaluation.objects.filter(week_number=week, year=year)
                .select_related("employee__user", "department")
                .annotate(
                    emp_id=F("employee__user__emp_id"),
                    employee_name=F("employee__user__first_name"),
                    department_name=F("department__name"),
                )
            )

            if not perf_qs.exists():
                return Response(
                    {"message": f"No performance data found for Week {week}, {year}."},
                    status=status.HTTP_200_OK,
                )

            feedback_map = {
                emp.id: get_feedback_average(emp)
                for emp in Employee.objects.filter(
                    id__in=perf_qs.values_list("employee_id", flat=True)
                )
            }

            ranked = perf_qs.annotate(
                computed_rank=Window(expression=Rank(), order_by=F("total_score").desc())
            )

            result = [
                {
                    "emp_id": obj.employee.user.emp_id,
                    "employee_full_name": f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip(),
                    "department": obj.department.name if obj.department else "-",
                    "total_score": obj.total_score,
                    "average_score": obj.average_score,
                    "feedback_avg": feedback_map.get(obj.employee.id, 0.0),
                    "week_number": week,
                    "year": year,
                    "rank": obj.computed_rank,
                    "remarks": obj.remarks or "",
                }
                for obj in ranked
            ]

            if save_cache:
                CachedReport.objects.create(
                    report_type="weekly",
                    year=year,
                    week_number=week,
                    payload={"records": result},
                    generated_by=request.user,
                )

            return Response(WeeklyReportSerializer(result, many=True).data, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ WeeklyReport Error:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================
# ✅ 2. MONTHLY CONSOLIDATED REPORT
# ===========================================================
class MonthlyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Returns monthly average performance summary."""
        try:
            month = int(request.query_params.get("month", timezone.now().month))
            year = int(request.query_params.get("year", timezone.now().year))
            save_cache = request.query_params.get("save_cache", "false").lower() == "true"

            perf_qs = PerformanceEvaluation.objects.filter(
                review_date__month=month, year=year
            ).select_related("employee__user", "department")

            if not perf_qs.exists():
                return Response(
                    {"message": f"No performance data found for {month}/{year}."},
                    status=status.HTTP_200_OK,
                )

            data = []
            for emp in Employee.objects.select_related("user", "department"):
                emp_perfs = perf_qs.filter(employee=emp)
                if not emp_perfs.exists():
                    continue

                avg_score = round(emp_perfs.aggregate(avg=Avg("average_score"))["avg"], 2)
                best_week_obj = emp_perfs.order_by("-average_score").first()
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
                CachedReport.objects.create(
                    report_type="monthly",
                    year=year,
                    month=month,
                    payload={"records": data},
                    generated_by=request.user,
                )

            return Response(MonthlyReportSerializer(data, many=True).data, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ MonthlyReport Error:", str(e))
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================
# ✅ 3. MANAGER-WISE WEEKLY REPORT
# ===========================================================
class ManagerReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Returns weekly performance report for employees under a manager."""
        manager_name = request.query_params.get("manager_name")
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        if not manager_name:
            return Response({"error": "Please provide manager_name."}, status=status.HTTP_400_BAD_REQUEST)

        employees = Employee.objects.filter(manager__user__first_name__iexact=manager_name)
        perf_qs = PerformanceEvaluation.objects.filter(
            employee__in=employees, week_number=week, year=year
        ).select_related("employee__user", "department")

        if not perf_qs.exists():
            return Response(
                {"message": f"No data found for manager {manager_name} in Week {week}, {year}."},
                status=status.HTTP_200_OK,
            )

        data = []
        for obj in perf_qs:
            emp = obj.employee
            fb_avg = get_feedback_average(emp)
            data.append({
                "manager_full_name": manager_name,
                "emp_id": emp.user.emp_id,
                "employee_full_name": f"{emp.user.first_name} {emp.user.last_name}",
                "department": emp.department.name if emp.department else "-",
                "total_score": obj.total_score,
                "average_score": obj.average_score,
                "feedback_avg": fb_avg,
                "week_number": week,
                "year": year,
                "rank": obj.rank,
                "remarks": obj.remarks,
            })

        return Response(ManagerReportSerializer(data, many=True).data, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 4. DEPARTMENT-WISE WEEKLY REPORT
# ===========================================================
class DepartmentReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Returns weekly performance report for a department."""
        department_name = request.query_params.get("department_name")
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        if not department_name:
            return Response({"error": "Please provide department_name."}, status=status.HTTP_400_BAD_REQUEST)

        employees = Employee.objects.filter(department__name__iexact=department_name)
        perf_qs = PerformanceEvaluation.objects.filter(
            employee__in=employees, week_number=week, year=year
        ).select_related("employee__user", "department", "manager__user")

        if not perf_qs.exists():
            return Response(
                {"message": f"No data found for department {department_name} in Week {week}, {year}."},
                status=status.HTTP_200_OK,
            )

        data = []
        for obj in perf_qs:
            emp = obj.employee
            fb_avg = get_feedback_average(emp)
            manager_full = (
                f"{emp.manager.user.first_name} {emp.manager.user.last_name}".strip()
                if emp.manager else "-"
            )
            data.append({
                "department_name": department_name,
                "emp_id": emp.user.emp_id,
                "employee_full_name": f"{emp.user.first_name} {emp.user.last_name}",
                "manager_full_name": manager_full,
                "total_score": obj.total_score,
                "average_score": obj.average_score,
                "feedback_avg": fb_avg,
                "week_number": week,
                "year": year,
                "rank": obj.rank,
                "remarks": obj.remarks,
            })

        return Response(DepartmentReportSerializer(data, many=True).data, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 5. EMPLOYEE PERFORMANCE HISTORY
# ===========================================================
class EmployeeHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        """Returns historical weekly trend for an employee."""
        try:
            employee = Employee.objects.select_related("user").get(user__emp_id=emp_id)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        perf_qs = PerformanceEvaluation.objects.filter(employee=employee).order_by("year", "week_number")
        if not perf_qs.exists():
            return Response({"message": "No performance history found."}, status=status.HTTP_200_OK)

        result = []
        for p in perf_qs:
            fb_avg = get_feedback_average(employee, start_date=p.created_at - timedelta(days=7), end_date=p.created_at)
            result.append({
                "week_number": p.week_number,
                "year": p.year,
                "average_score": p.average_score,
                "feedback_avg": fb_avg,
                "remarks": p.remarks,
                "rank": p.rank,
            })

        return Response(EmployeeHistorySerializer(result, many=True).data, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 6. EXPORT WEEKLY REPORT AS CSV
# ===========================================================
class ExportWeeklyCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Exports weekly report as a downloadable CSV."""
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        perf_qs = PerformanceEvaluation.objects.filter(
            week_number=week, year=year
        ).select_related("employee__user", "department")

        if not perf_qs.exists():
            return Response({"message": "No data found for CSV export."}, status=status.HTTP_200_OK)

        response = HttpResponse(content_type="text/csv")
        filename = f"Weekly_Report_Week{week}_{year}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(["Emp ID", "Employee Name", "Department", "Total Score", "Average Score", "Rank"])

        for p in perf_qs.order_by("-total_score"):
            writer.writerow([
                p.employee.user.emp_id,
                f"{p.employee.user.first_name} {p.employee.user.last_name}".strip(),
                p.department.name if p.department else "-",
                p.total_score,
                p.average_score,
                p.rank or "-",
            ])

        return response
