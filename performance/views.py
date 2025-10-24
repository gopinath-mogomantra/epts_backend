# ===============================================
# performance/views.py (Final Updated — 2025-10-24)
# ===============================================

from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Max, F, Avg, Window
from django.db.models.functions import Rank
from django.db import IntegrityError
from django.utils import timezone
import logging

from .models import PerformanceEvaluation
from .serializers import (
    PerformanceEvaluationSerializer,
    PerformanceCreateUpdateSerializer,
    PerformanceDashboardSerializer,
)
from employee.models import Employee
from notifications.models import Notification

logger = logging.getLogger(__name__)


# ==========================================================
# ✅ PERFORMANCE VIEWSET (CRUD + LIST)
# ==========================================================
class PerformanceEvaluationViewSet(viewsets.ModelViewSet):
    """
    Handles CRUD operations for performance evaluations.
    - Admins: Full access
    - Managers: Access to their team's evaluations
    - Employees: Can view only their own evaluations
    """
    queryset = PerformanceEvaluation.objects.select_related(
        "employee__user", "evaluator", "department"
    )
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["review_date", "total_score"]

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PerformanceCreateUpdateSerializer
        return PerformanceEvaluationSerializer

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", "").lower()
        qs = super().get_queryset()

        if role == "manager":
            return qs.filter(employee__manager__user=user)
        elif role == "employee":
            return qs.filter(employee__user=user)
        return qs

    # ------------------------------------------------------
    # ✅ CREATE (Supports emp_id, dept_code auto-detection)
    # ------------------------------------------------------
    def create(self, request, *args, **kwargs):
        role = getattr(request.user, "role", "").lower()
        if role not in ["admin", "manager"]:
            return Response(
                {"error": "Only Admin or Manager can create evaluations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        try:
            instance = serializer.save(evaluator=request.user)
        except IntegrityError:
            return Response(
                {"error": "Performance for this week already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("PerformanceEvaluation save failed: %s", exc)
            return Response(
                {"error": "Failed to save evaluation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ✅ Notification Trigger
        try:
            employee_user = instance.employee.user
            exists = Notification.objects.filter(
                employee=employee_user,
                message__icontains=str(instance.evaluation_period),
                is_read=False,
            ).exists()

            if not exists:
                Notification.objects.create(
                    employee=employee_user,
                    message=f"Your weekly performance for {instance.evaluation_period} has been published.",
                    auto_delete=True,
                )
        except Exception as e:
            logger.warning("Notification creation failed for evaluation %s: %s", instance.pk, e)

        # ✅ Frontend-Aligned Response
        emp = instance.employee.user
        evaluator = instance.evaluator
        dept = instance.department

        return Response(
            {
                "message": "✅ Performance evaluation recorded successfully.",
                "evaluation": {
                    "employee": {
                        "emp_id": emp.emp_id,
                        "name": f"{emp.first_name} {emp.last_name}".strip(),
                    },
                    "evaluator": (
                        {
                            "emp_id": evaluator.emp_id,
                            "name": f"{evaluator.first_name} {evaluator.last_name}".strip(),
                        }
                        if evaluator else None
                    ),
                    "department": (
                        {
                            "code": dept.code,
                            "name": dept.name,
                        }
                        if dept else None
                    ),
                    "evaluation_type": instance.evaluation_type,
                    "total_score": instance.total_score,
                    "average_score": instance.average_score,
                    "remarks": instance.remarks,
                    "evaluation_period": instance.evaluation_period,
                },
            },
            status=status.HTTP_201_CREATED,
        )


# ==========================================================
# ✅ PERFORMANCE SUMMARY (Leaderboard + Department Ranking)
# ==========================================================
class PerformanceSummaryView(APIView):
    """
    Weekly summary with optional rankings and department leaderboard.

    Query params:
      - include_rankings=true   -> include `leaderboard` and `department_ranking`
      - compare_previous=true   -> include change vs previous week (optional)
      - top_n=<int>             -> limit leaderboard size (default 10)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, "role", "").lower()

        if role not in ["admin", "manager"]:
            return Response(
                {"error": "Access denied. Only Admin or Manager can view summary."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Latest year/week
        latest_year = PerformanceEvaluation.objects.aggregate(max_year=Max("year"))["max_year"]
        if not latest_year:
            return Response({"message": "No performance records available."}, status=status.HTTP_200_OK)

        latest_week = (
            PerformanceEvaluation.objects.filter(year=latest_year)
            .aggregate(max_week=Max("week_number"))["max_week"]
        )
        if not latest_week:
            return Response({"message": "No performance records available."}, status=status.HTTP_200_OK)

        # Base data
        latest_qs = PerformanceEvaluation.objects.filter(
            year=latest_year, week_number=latest_week
        ).select_related("employee__user", "department")

        # Department averages
        dept_qs = (
            latest_qs.values("department__id", "department__name")
            .annotate(avg_score=Avg("average_score"))
            .order_by("-avg_score")
        )

        department_summary = []
        for d in dept_qs:
            dept_name = d["department__name"] or "N/A"
            avg_score = round(d["avg_score"] or 0, 2)
            top_in_dept = (
                latest_qs.filter(department__name=dept_name)
                .order_by("-total_score")
                .select_related("employee__user")
                .first()
            )
            department_summary.append({
                "department": dept_name,
                "avg_score": avg_score,
                "top_performer": (
                    f"{top_in_dept.employee.user.first_name} {top_in_dept.employee.user.last_name}".strip()
                    if top_in_dept and hasattr(top_in_dept, "employee")
                    else "-"
                ),
            })

        response_payload = {
            "evaluation_period": f"Week {latest_week}, {latest_year}",
            "department_average": round(latest_qs.aggregate(Avg("average_score"))["average_score__avg"] or 0, 2),
            "department_summary": department_summary,
        }

        # Leaderboard + Department Ranking
        include_rankings = request.query_params.get("include_rankings", "false").lower() == "true"
        if include_rankings:
            ranked_qs = latest_qs.annotate(
                computed_rank=Window(expression=Rank(), order_by=F("total_score").desc())
            ).order_by("computed_rank", "-total_score")

            top_n = int(request.query_params.get("top_n", 10))
            leaderboard = []
            for r in ranked_qs[:top_n]:
                u = r.employee.user
                leaderboard.append({
                    "rank": getattr(r, "computed_rank", None),
                    "emp_id": u.emp_id,
                    "name": f"{u.first_name} {u.last_name}".strip(),
                    "department": r.department.name if r.department else None,
                    "total_score": r.total_score,
                    "average_score": r.average_score,
                    "evaluation_type": r.evaluation_type,
                    "review_date": r.review_date,
                })

            department_ranking = []
            for idx, d in enumerate(dept_qs):
                department_ranking.append({
                    "department": d["department__name"] or "N/A",
                    "avg_score": round(d["avg_score"] or 0, 2),
                    "department_rank": idx + 1,
                })

            response_payload["leaderboard"] = leaderboard
            response_payload["department_ranking"] = department_ranking

        # Optional compare previous week
        if request.query_params.get("compare_previous", "false").lower() == "true":
            prev_week = latest_week - 1
            prev_year = latest_year
            if prev_week <= 0:
                prev_year = latest_year - 1
                prev_week = (
                    PerformanceEvaluation.objects.filter(year=prev_year)
                    .aggregate(max_week=Max("week_number"))["max_week"]
                    or 0
                )

            prev_qs = PerformanceEvaluation.objects.filter(year=prev_year, week_number=prev_week)
            prev_dept_avgs = {
                x["department__name"] or "N/A": float(x["avg_score"] or 0)
                for x in prev_qs.values("department__name").annotate(avg_score=Avg("average_score"))
            }

            for d in response_payload["department_summary"]:
                prev_avg = prev_dept_avgs.get(d["department"], 0)
                change = None
                if prev_avg:
                    try:
                        change = round(((d["avg_score"] - prev_avg) / prev_avg) * 100, 2)
                    except Exception:
                        change = None
                d["previous_week_avg"] = round(prev_avg, 2)
                d["change_percent_vs_previous_week"] = change

            response_payload["previous_week"] = {
                "week_number": prev_week,
                "year": prev_year,
            }

        return Response(response_payload, status=status.HTTP_200_OK)


# ==========================================================
# ✅ EMPLOYEE DASHBOARD (Self Performance View)
# ==========================================================
class EmployeeDashboardView(APIView):
    """
    Displays the logged-in employee's performance summary:
    - Overall average
    - Best week
    - Trend data (weekly scores)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            employee = Employee.objects.select_related("user").get(user=user)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        evaluations = PerformanceEvaluation.objects.filter(employee=employee).order_by("-review_date")

        if not evaluations.exists():
            return Response({"message": "No performance records found."}, status=status.HTTP_200_OK)

        avg_score = round(evaluations.aggregate(Avg("average_score"))["average_score__avg"] or 0, 2)
        best = evaluations.order_by("-total_score").first()
        trend_data = list(evaluations.values("week_number", "average_score").order_by("week_number"))

        serializer = PerformanceDashboardSerializer(evaluations, many=True, context={"request": request})

        return Response(
            {
                "employee": f"{user.first_name} {user.last_name}".strip(),
                "emp_id": user.emp_id,
                "overall_average": avg_score,
                "best_week": {
                    "evaluation_period": best.evaluation_period,
                    "average_score": best.average_score,
                },
                "trend_data": trend_data,
                "evaluations": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ==========================================================
# ✅ EMPLOYEE PERFORMANCE DETAIL (Admin/Manager Access)
# ==========================================================
class EmployeePerformanceView(APIView):
    """
    Fetches all or specific week's evaluations for a given employee.
    Accessible by Admins and Managers.
    Query params: ?evaluation_period=Week 43, 2025
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        user = request.user
        role = getattr(user, "role", "").lower()

        if role not in ["admin", "manager"]:
            return Response(
                {"error": "Only Admin or Manager can view employee performance."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            employee = Employee.objects.select_related("user", "department", "manager__user").get(
                user__emp_id=emp_id
            )
        except Employee.DoesNotExist:
            return Response(
                {"error": f"No employee found with ID {emp_id}."},
                status=status.HTTP_404_NOT_FOUND,
            )

        evaluation_period = request.query_params.get("evaluation_period")
        qs = PerformanceEvaluation.objects.filter(employee=employee).order_by("-review_date")
        if evaluation_period:
            qs = qs.filter(evaluation_period__iexact=evaluation_period)

        if not qs.exists():
            return Response(
                {"message": f"No evaluations found for {employee.user.first_name}."},
                status=status.HTTP_200_OK,
            )

        serializer = PerformanceEvaluationSerializer(qs, many=True, context={"request": request})

        header_info = {
            "emp_id": employee.user.emp_id,
            "employee_name": f"{employee.user.first_name} {employee.user.last_name}".strip(),
            "department": employee.department.name if employee.department else None,
            "manager_name": (
                f"{employee.manager.user.first_name} {employee.manager.user.last_name}".strip()
                if employee.manager else None
            ),
            "available_weeks": list(qs.values_list("evaluation_period", flat=True)),
        }

        return Response(
            {"header": header_info, "evaluations": serializer.data},
            status=status.HTTP_200_OK,
        )
