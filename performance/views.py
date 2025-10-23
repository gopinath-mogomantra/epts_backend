# ===============================================
# performance/views.py (Final Fixed & Enhanced)
# ===============================================

from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Max, F, Avg, Window
from django.db.models.functions import Rank
from django.db import IntegrityError
from django.utils import timezone

from .models import PerformanceEvaluation
from .serializers import (
    PerformanceEvaluationSerializer,
    PerformanceCreateUpdateSerializer,
    PerformanceDashboardSerializer,
)
from employee.models import Employee


# ==========================================================
# ✅ 1. PERFORMANCE VIEWSET (CRUD + LIST)
# ==========================================================
class PerformanceEvaluationViewSet(viewsets.ModelViewSet):
    """
    Handles CRUD operations for performance evaluations.
    - Admins: Full access
    - Managers: Access to their team's evaluations
    - Employees: View only their own evaluations
    """
    queryset = PerformanceEvaluation.objects.select_related(
        "employee__user", "evaluator", "department"
    ).all()
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
        
        employee = serializer.validated_data.get("employee")
        if employee and not serializer.validated_data.get("department"):
            serializer.validated_data["department"] = employee.department

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            instance = serializer.save(evaluator=request.user)
        except IntegrityError:
            return Response(
                {"error": "Performance for this week already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "✅ Performance evaluation recorded successfully.",
                "data": PerformanceEvaluationSerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ==========================================================
# ✅ 2. PERFORMANCE SUMMARY (TOP 3 / WEAK 3 + DEPT SUMMARY)
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

        # 🔹 Get latest week and year
        latest_year = PerformanceEvaluation.objects.aggregate(max_year=Max("year"))["max_year"]
        latest_week = (
            PerformanceEvaluation.objects.filter(year=latest_year)
            .aggregate(max_week=Max("week_number"))["max_week"]
        )

        if not latest_week:
            return Response({"message": "No performance records available."}, status=200)

        # 🔹 Fetch latest evaluations
        latest_evals = PerformanceEvaluation.objects.filter(
            year=latest_year, week_number=latest_week
        ).select_related("employee__user", "department")

        # 🔹 Compute ranks safely (avoid model field conflict)
        ranked_evals = latest_evals.annotate(
            computed_rank=Window(
                expression=Rank(),
                order_by=F("total_score").desc(),
            )
        ).order_by("computed_rank")

        # ✅ Ensure unique, non-overlapping top & weak performers
        top_3 = list(ranked_evals[:3])
        weak_3 = [e for e in ranked_evals.order_by("total_score") if e not in top_3][:3]

        # 🔹 Helper function to serialize employee details
        def serialize(emp):
            user = emp.employee.user
            return {
                "emp_id": user.emp_id,
                "employee_name": f"{user.first_name} {user.last_name}".strip(),
                "department": emp.department.name if emp.department else "N/A",
                "total_score": emp.total_score,
                "average_score": emp.average_score,
                "evaluation_type": emp.evaluation_type,
                "review_date": emp.review_date,
                "rank": getattr(emp, "computed_rank", None),
            }

        # 🔹 Compute department average
        dept_avg = round(latest_evals.aggregate(Avg("average_score"))["average_score__avg"], 2)

        # ==========================================================
        # 🔹 Department-wise summary
        # ==========================================================
        dept_summary = (
            latest_evals.values("department__name")
            .annotate(avg_score=Avg("average_score"))
            .order_by("department__name")
        )

        department_summary = []
        for d in dept_summary:
            dept_name = d["department__name"] or "N/A"
            top_in_dept = (
                latest_evals.filter(department__name=dept_name)
                .order_by("-total_score")
                .first()
            )
            department_summary.append({
                "department": dept_name,
                "avg_score": round(d["avg_score"], 2) if d["avg_score"] else 0,
                "top_performer": (
                    f"{top_in_dept.employee.user.first_name} {top_in_dept.employee.user.last_name}".strip()
                    if top_in_dept and hasattr(top_in_dept, "employee")
                    else "-"
                )
            })

        # 🔹 Final Response
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
# ✅ 3. EMPLOYEE DASHBOARD (SELF PERFORMANCE VIEW)
# ==========================================================
class EmployeeDashboardView(APIView):
    """
    Shows an employee's personal performance dashboard.
    Includes average, best week, and trend chart data.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            employee = Employee.objects.get(user=user)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        evaluations = (
            PerformanceEvaluation.objects.filter(employee=employee)
            .order_by("-review_date")
        )

        if not evaluations.exists():
            return Response({"message": "No performance records found."}, status=200)

        avg_score = round(evaluations.aggregate(Avg("average_score"))["average_score__avg"], 2)
        best = evaluations.order_by("-total_score").first()

        trend_data = evaluations.values("week_number", "average_score").order_by("week_number")
        serializer = PerformanceDashboardSerializer(evaluations, many=True)

        return Response(
            {
                "employee": f"{user.first_name} {user.last_name}".strip(),
                "emp_id": user.emp_id,
                "overall_average": avg_score,
                "best_week": {
                    "evaluation_period": best.evaluation_period,
                    "average_score": best.average_score,
                },
                "trend_data": list(trend_data),
                "evaluations": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
