# ===============================================
# reports/views.py
# ===============================================
# Handles Weekly, Monthly, and Employee History Reports
# Combines data from Employee, Performance, and Feedback apps
# ===============================================

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.db.models import Avg, F, Q, Window
from django.db.models.functions import Rank
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
import csv

from employee.models import Employee
from performance.models import PerformanceEvaluation
from feedback.models import GeneralFeedback, ManagerFeedback, ClientFeedback
from .models import CachedReport
from .serializers import (
    WeeklyReportSerializer,
    MonthlyReportSerializer,
    EmployeeHistorySerializer,
)


# ===========================================================
# 🧠 Helper: Calculate Feedback Average for an Employee
# ===========================================================
def get_feedback_average(employee, start_date=None, end_date=None):
    """Compute average rating from all feedback sources for a given employee."""
    fb_qs = Q(employee=employee)
    if start_date and end_date:
        fb_qs &= Q(created_at__range=(start_date, end_date))

    ratings = list(
        GeneralFeedback.objects.filter(fb_qs).values_list("rating", flat=True)
    ) + list(
        ManagerFeedback.objects.filter(fb_qs).values_list("rating", flat=True)
    ) + list(
        ClientFeedback.objects.filter(fb_qs).values_list("rating", flat=True)
    )
    return round(sum(ratings) / len(ratings), 2) if ratings else 0.0


# ===========================================================
# ✅ 1. WEEKLY CONSOLIDATED REPORT
# ===========================================================
class WeeklyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Returns weekly performance summary for all employees."""
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
                status=status.HTTP_204_NO_CONTENT,
            )

        # Feedback averages for each employee
        feedback_map = {
            emp.id: get_feedback_average(emp)
            for emp in Employee.objects.filter(
                id__in=perf_qs.values_list("employee_id", flat=True)
            )
        }

        ranked = perf_qs.annotate(
            rank=Window(expression=Rank(), order_by=F("total_score").desc())
        ).order_by("rank")

        result = [
            {
                "emp_id": obj.employee.user.emp_id,
                "employee_name": f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip(),
                "department": obj.department.name if obj.department else "-",
                "total_score": obj.total_score,
                "average_score": obj.average_score,
                "feedback_avg": feedback_map.get(obj.employee.id, 0),
                "week_number": week,
                "year": year,
                "rank": obj.rank,
            }
            for obj in ranked
        ]

        # Optional: save cached report
        if save_cache:
            CachedReport.objects.create(
                report_type="weekly",
                year=year,
                week_number=week,
                payload={"records": result},
                generated_by=request.user,
            )

        serializer = WeeklyReportSerializer(result, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 2. MONTHLY CONSOLIDATED REPORT
# ===========================================================
class MonthlyReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Returns monthly average performance summary."""
        month = int(request.query_params.get("month", timezone.now().month))
        year = int(request.query_params.get("year", timezone.now().year))
        save_cache = request.query_params.get("save_cache", "false").lower() == "true"

        perf_qs = PerformanceEvaluation.objects.filter(
            review_date__month=month, year=year
        ).select_related("employee__user", "department")

        if not perf_qs.exists():
            return Response(
                {"message": f"No performance data found for {month}/{year}."},
                status=status.HTTP_204_NO_CONTENT,
            )

        data = []
        for emp in Employee.objects.select_related("user", "department"):
            emp_perfs = perf_qs.filter(employee=emp)
            if not emp_perfs.exists():
                continue

            avg_score = round(emp_perfs.aggregate(avg=Avg("average_score"))["avg"], 2)
            best_week_obj = emp_perfs.order_by("-average_score").first()
            fb_avg = get_feedback_average(emp, start_date=best_week_obj.created_at - timedelta(days=30), end_date=best_week_obj.created_at)

            data.append({
                "emp_id": emp.user.emp_id,
                "employee_name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
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

        serializer = MonthlyReportSerializer(data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 3. EMPLOYEE PERFORMANCE HISTORY (TREND)
# ===========================================================
class EmployeeHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        """Returns historical weekly trend for one employee."""
        try:
            employee = Employee.objects.select_related("user").get(user__emp_id=emp_id)
        except Employee.DoesNotExist:
            return Response({"error": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        perf_qs = PerformanceEvaluation.objects.filter(employee=employee).order_by("year", "week_number")
        if not perf_qs.exists():
            return Response({"message": "No performance history found."}, status=status.HTTP_204_NO_CONTENT)

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

        serializer = EmployeeHistorySerializer(result, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 4. EXPORT WEEKLY REPORT AS CSV
# ===========================================================
class ExportWeeklyCSVView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Exports weekly report as a downloadable CSV file."""
        week = int(request.query_params.get("week", timezone.now().isocalendar()[1]))
        year = int(request.query_params.get("year", timezone.now().year))

        perf_qs = PerformanceEvaluation.objects.filter(week_number=week, year=year)
        if not perf_qs.exists():
            return Response({"message": "No data found for CSV export."}, status=status.HTTP_204_NO_CONTENT)

        response = HttpResponse(content_type="text/csv")
        filename = f"Weekly_Report_Week{week}_{year}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(["Emp ID", "Employee Name", "Department", "Total Score", "Average Score", "Rank"])

        for p in perf_qs.select_related("employee__user", "department").order_by("-total_score"):
            writer.writerow([
                p.employee.user.emp_id,
                f"{p.employee.user.first_name} {p.employee.user.last_name}",
                p.department.name if p.department else "-",
                p.total_score,
                p.average_score,
                p.rank or "-",
            ])

        return response
