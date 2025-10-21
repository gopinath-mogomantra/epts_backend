# ===============================================
# performance/views.py (Final Polished Version)
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
# ✅ 2. PERFORMANCE SUMMARY (TOP 3 / WEAK 3)
# ==========================================================
class PerformanceSummaryView(APIView):
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
            return Response({"message": "No performance records available."}, status=200)

        latest_evals = PerformanceEvaluation.objects.filter(
            year=latest_year, week_number=latest_week
        ).select_related("employee__user", "department")

        ranked_evals = latest_evals.annotate(
            rank=Window(expression=Rank(), order_by=F("total_score").desc())
        ).order_by("rank")

        top_3 = ranked_evals[:3]
        weak_3 = ranked_evals.order_by("total_score")[:3]

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
                "rank": getattr(emp, "rank", None),
            }

        dept_avg = round(latest_evals.aggregate(Avg("average_score"))["average_score__avg"], 2)

        return Response(
            {
                "evaluation_period": f"Week {latest_week}, {latest_year}",
                "department_average": dept_avg,
                "top_performers": [serialize(e) for e in top_3],
                "weak_performers": [serialize(e) for e in weak_3],
            },
            status=status.HTTP_200_OK,
        )


# ==========================================================
# ✅ 3. EMPLOYEE DASHBOARD (SELF PERFORMANCE VIEW)
# ==========================================================
class EmployeeDashboardView(APIView):
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
