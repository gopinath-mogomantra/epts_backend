# ===============================================
# performance/views.py
# ===============================================
# Handles CRUD for Performance Evaluations
# Includes summary (Top/Weak performers) and
# dashboard endpoints for employees.
# ===============================================

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Max
from django.shortcuts import get_object_or_404

from .models import PerformanceEvaluation
from .serializers import (
    PerformanceEvaluationSerializer,
    PerformanceCreateUpdateSerializer,
    PerformanceDashboardSerializer,
)
from employee.models import Employee


# ==========================================================
# ✅ 1. LIST + CREATE VIEW
# ==========================================================
class PerformanceListCreateView(generics.ListCreateAPIView):
    """
    GET  -> List all performance evaluations (Admin/Manager)
    POST -> Create a new evaluation record (Admin/Manager)
    """
    queryset = PerformanceEvaluation.objects.select_related(
        "employee", "evaluator", "department"
    ).all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return PerformanceCreateUpdateSerializer
        return PerformanceEvaluationSerializer

    def create(self, request, *args, **kwargs):
        """Allow only Admin/Manager to create new evaluations."""
        user = request.user
        user_role = getattr(user, "role", None)

        if str(user_role).lower() not in ["admin", "manager"]:
            return Response(
                {"error": "Only Admin or Manager can create evaluations."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(evaluator=request.user)

        return Response(
            {
                "message": "✅ Performance evaluation recorded successfully.",
                "data": PerformanceEvaluationSerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ==========================================================
# ✅ 2. DETAIL VIEW (GET SINGLE RECORD)
# ==========================================================
class PerformanceDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific performance evaluation by ID.
    """
    queryset = PerformanceEvaluation.objects.select_related(
        "employee", "evaluator", "department"
    ).all()
    serializer_class = PerformanceEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]


# ==========================================================
# ✅ 3. PERFORMANCE SUMMARY (TOP 3 & WEAK 3)
# ==========================================================
class PerformanceSummaryView(APIView):
    """
    Returns Top 3 and Weak 3 performers based on their latest total_score.
    Used for Admin/Manager dashboards.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if str(getattr(user, "role", "")).lower() not in ["admin", "manager"]:
            return Response(
                {"error": "Access denied. Only Admin or Manager can view summary."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get latest evaluation per employee
        latest_evals = (
            PerformanceEvaluation.objects.values("employee")
            .annotate(latest_date=Max("review_date"))
        )

        # Fetch the corresponding evaluation records
        latest_records = PerformanceEvaluation.objects.filter(
            review_date__in=[item["latest_date"] for item in latest_evals]
        ).select_related("employee__user", "department")

        # Sort by total_score descending
        sorted_records = sorted(latest_records, key=lambda x: x.total_score, reverse=True)

        top_3 = sorted_records[:3]
        weak_3 = sorted_records[-3:] if len(sorted_records) >= 3 else sorted_records

        def format_data(obj):
            user = obj.employee.user
            return {
                "emp_id": getattr(user, "emp_id", None),
                "name": f"{user.first_name} {user.last_name}".strip(),
                "department": getattr(obj.department, "name", "N/A") if obj.department else "N/A",
                "total_score": obj.total_score,
                "evaluation_type": obj.evaluation_type,
                "review_date": obj.review_date,
            }

        return Response(
            {
                "top_performers": [format_data(e) for e in top_3],
                "weak_performers": [format_data(e) for e in weak_3],
            },
            status=status.HTTP_200_OK,
        )


# ==========================================================
# ✅ 4. EMPLOYEE DASHBOARD (SELF PERFORMANCE VIEW)
# ==========================================================
class EmployeeDashboardView(APIView):
    """
    Displays logged-in employee’s own performance history.
    Each record shows evaluation type, score, remarks, etc.
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

        serializer = PerformanceDashboardSerializer(evaluations, many=True)
        return Response({"evaluations": serializer.data}, status=status.HTTP_200_OK)
