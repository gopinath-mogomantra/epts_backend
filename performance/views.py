# ===============================================
# performance/views.py (Final Synced Version)
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

    def create(self, request, *args, **kwargs):
        role = getattr(request.user, "role", "").lower()
        if role not in ["admin", "manager"]:
            return Response(
                {"error": "Only Admin or Manager can create evaluations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        employee = serializer.validated_data.get("employee")

        # Auto-infer department if missing
        if employee and not serializer.validated_data.get("department"):
            serializer.validated_data["department"] = employee.department

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

        return Response(
            {
                "message": "✅ Performance evaluation recorded successfully.",
                "data": PerformanceEvaluationSerializer(instance, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ==========================================================
# ✅ PERFORMANCE SUMMARY (Top 3 / Weak 3 / Dept Summary)
# ==========================================================
class PerformanceSummaryView(APIView):
    """
    Provides weekly summary insights:
    - Top 3 performers
    - Weak 3 performers
    - Department averages and top performers
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

        latest_year = PerformanceEvaluation.objects.aggregate(max_year=Max("year"))["max_year"]
        latest_week = (
            PerformanceEvaluation.objects.filter(year=latest_year)
            .aggregate(max_week=Max("week_number"))["max_week"]
        )

        if not latest_week:
            return Response({"message": "No performance records available."}, status=status.HTTP_200_OK)

        # Fetch current week data
        latest_evals = PerformanceEvaluation.objects.filter(
            year=latest_year, week_number=latest_week
        ).select_related("employee__user", "department")

        ranked_evals = latest_evals.annotate(
            computed_rank=Window(expression=Rank(), order_by=F("total_score").desc())
        ).order_by("computed_rank")

        # Top 3 and Weak 3
        top_3 = list(ranked_evals[:3])
        weak_3 = list(latest_evals.order_by("total_score")[:3])

        def serialize(emp):
            u = emp.employee.user
            return {
                "emp_id": u.emp_id,
                "employee_name": f"{u.first_name} {u.last_name}".strip(),
                "department": emp.department.name if emp.department else "N/A",
                "total_score": emp.total_score,
                "average_score": emp.average_score,
                "evaluation_type": emp.evaluation_type,
                "review_date": emp.review_date,
                "rank": getattr(emp, "computed_rank", None),
            }

        dept_avg = round(latest_evals.aggregate(Avg("average_score"))["average_score__avg"] or 0, 2)
        dept_summary_qs = (
            latest_evals.values("department__name")
            .annotate(avg_score=Avg("average_score"))
            .order_by("department__name")
        )

        department_summary = []
        for d in dept_summary_qs:
            dept_name = d["department__name"] or "N/A"
            top_in_dept = (
                latest_evals.filter(department__name=dept_name).order_by("-total_score").first()
            )
            department_summary.append({
                "department": dept_name,
                "avg_score": round(d["avg_score"] or 0, 2),
                "top_performer": (
                    f"{top_in_dept.employee.user.first_name} {top_in_dept.employee.user.last_name}".strip()
                    if top_in_dept and hasattr(top_in_dept, "employee")
                    else "-"
                ),
            })

        return Response(
            {
                "evaluation_period": f"Week {latest_week}, {latest_year}",
                "department_average": dept_avg,
                "department_summary": department_summary,
                "top_performers": [serialize(e) for e in top_3],
                "weak_performers": [serialize(e) for e in weak_3],
            },
            status=status.HTTP_200_OK,
        )


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

        trend_data = list(
            evaluations.values("week_number", "average_score").order_by("week_number")
        )

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
