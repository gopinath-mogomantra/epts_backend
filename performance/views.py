# ===========================================================
# performance/views.py  (Final Updated — Frontend & API Validation Ready)
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
    # ✅ CREATE — Frontend Safe & Validation Friendly
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

        # Notification (safe execution)
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
                    "evaluator": (
                        {
                            "emp_id": instance.evaluator.emp_id,
                            "name": f"{instance.evaluator.first_name} {instance.evaluator.last_name}".strip(),
                        }
                        if instance.evaluator else None
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


# ===========================================================
# ✅ GET PERFORMANCE RECORDS BY EMPLOYEE ID
# ===========================================================
class EmployeePerformanceByIdView(APIView):
    """
    Returns all performance evaluations for a specific employee.
    Supports optional week/year filters.
    Example:
      GET /api/performance/evaluations/EMP0028/
      GET /api/performance/evaluations/EMP0028/?week=43&year=2025
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        role = getattr(request.user, "role", "").lower()

        # Allow Admin, Manager, or the Employee themself
        if role not in ["admin", "manager", "employee"]:
            return Response(
                {"error": "Access denied."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 🔍 Employee lookup
        try:
            emp = Employee.objects.select_related("user", "department").get(user__emp_id=emp_id)
        except Employee.DoesNotExist:
            return Response({"error": f"Employee '{emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        # 🔐 Employee role restriction (can only see self)
        if role == "employee" and request.user.emp_id != emp_id:
            return Response(
                {"error": "Employees can only view their own performance data."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 🔍 Filter evaluations
        qs = PerformanceEvaluation.objects.filter(employee=emp).order_by("-review_date")
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

        serializer = PerformanceEvaluationSerializer(qs, many=True)

        return Response(
            {
                "employee": {
                    "emp_id": emp.user.emp_id,
                    "name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                    "department": emp.department.name if emp.department else "-",
                },
                "record_count": qs.count(),
                "evaluations": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ✅ PERFORMANCE SUMMARY (Admin / Manager Dashboard)
# ===========================================================
class PerformanceSummaryView(APIView):
    """
    Provides weekly department summary and leaderboard.
    Query Params:
      ?include_rankings=true
      ?compare_previous=true
      ?top_n=10
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, "role", "").lower()
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

        dept_avg = (
            qs.values("department__id", "department__name")
            .annotate(avg_score=Avg("average_score"))
            .order_by("-avg_score")
        )

        summary = []
        for dept in dept_avg:
            dname = dept["department__name"] or "N/A"
            avg_score = round(dept["avg_score"] or 0, 2)
            top_emp = (
                qs.filter(department__name=dname)
                .order_by("-total_score")
                .select_related("employee__user")
                .first()
            )
            summary.append({
                "department": dname,
                "average_score": avg_score,
                "top_performer": (
                    f"{top_emp.employee.user.first_name} {top_emp.employee.user.last_name}".strip()
                    if top_emp else "-"
                ),
            })

        response = {
            "evaluation_period": f"Week {latest_week}, {latest_year}",
            "overall_avg_score": round(qs.aggregate(Avg("average_score"))["average_score__avg"] or 0, 2),
            "department_summary": summary,
        }

        # Rankings
        if request.query_params.get("include_rankings", "false").lower() == "true":
            ranked_qs = qs.annotate(
                rank_position=Window(expression=Rank(), order_by=F("total_score").desc())
            ).order_by("rank_position")

            top_n = int(request.query_params.get("top_n", 10))
            leaderboard = []
            for r in ranked_qs[:top_n]:
                u = r.employee.user
                leaderboard.append({
                    "rank": getattr(r, "rank_position", None),
                    "emp_id": u.emp_id,
                    "name": f"{u.first_name} {u.last_name}".strip(),
                    "department": r.department.name if r.department else None,
                    "average_score": r.average_score,
                })

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
        best = records.order_by("-total_score").first()

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
