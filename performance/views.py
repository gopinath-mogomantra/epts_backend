# ===========================================================
# performance/views.py (Final Enhanced — Ranking + Summary Ready)
# ===========================================================

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
    PerformanceRankSerializer,
)
from employee.models import Employee
from notifications.models import Notification

logger = logging.getLogger(__name__)

# ===========================================================
# ✅ PERFORMANCE VIEWSET (CRUD + FILTERS)
# ===========================================================
class PerformanceEvaluationViewSet(viewsets.ModelViewSet):
    """
    CRUD APIs for Performance Evaluations.
    - Admin: Full Access
    - Manager: Own Team
    - Employee: Own Records
    """

    queryset = PerformanceEvaluation.objects.select_related(
        "employee__user", "evaluator", "department"
    )
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["review_date", "total_score", "average_score"]
    ordering = ["-review_date"]

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

    # --------------------------------------------------------
    # ✅ CREATE — Auto Rank Trigger + Notification
    # --------------------------------------------------------
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
            instance = serializer.save()
            instance.auto_rank_trigger()  # ✅ Auto rank calculation
        except IntegrityError:
            return Response(
                {"error": "A performance record already exists for this week and evaluator."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Error saving performance evaluation: %s", exc)
            return Response(
                {"error": "Something went wrong while saving the evaluation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Optional Notification
        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=f"Your weekly performance for {instance.evaluation_period} has been published.",
                auto_delete=True,
            )
        except Exception as e:
            logger.warning("⚠️ Notification failed: %s", e)

        return Response(
            {
                "message": "✅ Performance evaluation recorded successfully.",
                "evaluation": {
                    "employee": {
                        "emp_id": instance.employee.user.emp_id,
                        "name": f"{instance.employee.user.first_name} {instance.employee.user.last_name}".strip(),
                    },
                    "department": (
                        {"code": instance.department.code, "name": instance.department.name}
                        if instance.department else None
                    ),
                    "average_score": instance.average_score,
                    "rank": instance.rank,
                    "remarks": instance.remarks,
                    "evaluation_period": instance.evaluation_period,
                },
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# ✅ GET PERFORMANCE RECORDS BY EMPLOYEE ID (With Rank)
# ===========================================================
class EmployeePerformanceByIdView(APIView):
    """
    Returns all performance evaluations for a specific employee.
    Supports optional week/year filters.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        role = getattr(request.user, "role", "").lower()

        if role not in ["admin", "manager", "employee"]:
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            emp = Employee.objects.select_related("user", "department").get(user__emp_id=emp_id)
        except Employee.DoesNotExist:
            return Response({"error": f"Employee '{emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        if role == "employee" and request.user.emp_id != emp_id:
            return Response(
                {"error": "Employees can only view their own performance data."},
                status=status.HTTP_403_FORBIDDEN,
            )

        qs = PerformanceEvaluation.objects.filter(employee=emp).select_related("employee__user", "department")

        week = request.query_params.get("week")
        year = request.query_params.get("year")
        if week:
            qs = qs.filter(week_number=week)
        if year:
            qs = qs.filter(year=year)

        if not qs.exists():
            return Response(
                {"message": f"No performance data found for employee {emp_id}."},
                status=status.HTTP_200_OK,
            )

        ranked_qs = qs.annotate(
            computed_rank=Window(expression=Rank(), order_by=F("average_score").desc())
        ).order_by("-average_score")

        serializer = PerformanceEvaluationSerializer(ranked_qs, many=True)
        return Response(
            {
                "employee": {
                    "emp_id": emp.user.emp_id,
                    "name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                    "department": emp.department.name if emp.department else "-",
                },
                "record_count": ranked_qs.count(),
                "evaluations": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ✅ PERFORMANCE SUMMARY (Admin / Manager Dashboard)
# ===========================================================
class PerformanceSummaryView(APIView):
    """
    Weekly summary of departments and leaderboard.
    Includes:
      - Overall Department Avg
      - Top 3 Performers
      - Weak 3 Performers
      - Leaderboard (optional ?include_rankings=true)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user, "role", "").lower()
        if role not in ["admin", "manager"]:
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        latest_year = PerformanceEvaluation.objects.aggregate(max_year=Max("year"))["max_year"]
        if not latest_year:
            return Response({"message": "No performance data yet."}, status=status.HTTP_200_OK)

        latest_week = (
            PerformanceEvaluation.objects.filter(year=latest_year)
            .aggregate(max_week=Max("week_number"))["max_week"]
        )
        if not latest_week:
            return Response({"message": "No weekly data found."}, status=status.HTTP_200_OK)

        qs = PerformanceEvaluation.objects.filter(year=latest_year, week_number=latest_week).select_related(
            "employee__user", "department"
        )

        overall_avg = round(qs.aggregate(Avg("average_score"))["average_score__avg"] or 0, 2)
        dept_summary = (
            qs.values("department__name")
            .annotate(avg_score=Avg("average_score"))
            .order_by("-avg_score")
        )

        # 🔹 Department Summaries
        departments = []
        for d in dept_summary:
            dname = d["department__name"] or "N/A"
            avg_score = round(d["avg_score"], 2)
            departments.append({"department": dname, "average_score": avg_score})

        # 🔹 Top 3 and Weak 3
        top_3 = qs.order_by("-average_score")[:3]
        weak_3 = qs.order_by("average_score")[:3]

        from .serializers import PerformanceRankSerializer
        top_serialized = PerformanceRankSerializer(top_3, many=True).data
        weak_serialized = PerformanceRankSerializer(weak_3, many=True).data

        response = {
            "evaluation_period": f"Week {latest_week}, {latest_year}",
            "overall_average": overall_avg,
            "department_summary": departments,
            "top_3": top_serialized,
            "weak_3": weak_serialized,
        }

        # 🔹 Leaderboard (Optional)
        if request.query_params.get("include_rankings", "false").lower() == "true":
            ranked_qs = qs.annotate(rank_position=Window(expression=Rank(), order_by=F("average_score").desc()))
            leaderboard = PerformanceRankSerializer(ranked_qs[:10], many=True).data
            response["leaderboard"] = leaderboard

        return Response(response, status=status.HTTP_200_OK)


# ===========================================================
# ✅ EMPLOYEE DASHBOARD (Self Performance Summary)
# ===========================================================
class EmployeeDashboardView(APIView):
    """Displays logged-in employee’s personal performance trend."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            employee = Employee.objects.select_related("user").get(user=user)
        except Employee.DoesNotExist:
            return Response({"error": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)

        records = PerformanceEvaluation.objects.filter(employee=employee).order_by("-review_date")
        if not records.exists():
            return Response({"message": "No performance data found."}, status=status.HTTP_200_OK)

        avg_score = round(records.aggregate(Avg("average_score"))["average_score__avg"] or 0, 2)
        best = records.order_by("-average_score").first()
        serializer = PerformanceDashboardSerializer(records, many=True)

        return Response(
            {
                "employee": {
                    "emp_id": user.emp_id,
                    "name": f"{user.first_name} {user.last_name}".strip(),
                },
                "overall_average": avg_score,
                "best_week": {
                    "evaluation_period": best.evaluation_period,
                    "average_score": best.average_score,
                },
                "trend_data": list(records.values("week_number", "average_score").order_by("week_number")),
                "evaluations": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ✅ ADMIN / MANAGER: VIEW EMPLOYEE PERFORMANCE
# ===========================================================
class EmployeePerformanceView(APIView):
    """View all or specific evaluations for a given employee."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        role = getattr(request.user, "role", "").lower()
        if role not in ["admin", "manager"]:
            return Response(
                {"error": "Only Admin or Manager can view this data."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            emp = Employee.objects.select_related("user", "department", "manager__user").get(user__emp_id=emp_id)
        except Employee.DoesNotExist:
            return Response({"error": f"Employee '{emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        qs = PerformanceEvaluation.objects.filter(employee=emp).order_by("-review_date")
        period = request.query_params.get("evaluation_period")
        if period:
            qs = qs.filter(evaluation_period__iexact=period)

        if not qs.exists():
            return Response({"message": "No records found."}, status=status.HTTP_200_OK)

        serializer = PerformanceEvaluationSerializer(qs, many=True)
        header = {
            "emp_id": emp.user.emp_id,
            "employee_name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
            "department": emp.department.name if emp.department else None,
            "manager": (
                f"{emp.manager.user.first_name} {emp.manager.user.last_name}".strip()
                if emp.manager else None
            ),
            "available_weeks": list(qs.values_list("evaluation_period", flat=True)),
        }

        return Response({"header": header, "evaluations": serializer.data}, status=status.HTTP_200_OK)
