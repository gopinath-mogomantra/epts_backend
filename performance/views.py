# performance/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from .models import PerformanceEvaluation
from .serializers import (
    PerformanceEvaluationSerializer,
    PerformanceCreateUpdateSerializer
)

User = get_user_model()


# -----------------------------
# CRUD Views
# -----------------------------
class PerformanceListCreateView(generics.ListCreateAPIView):
    """
    GET  -> List all employee performance evaluations
    POST -> Create a new evaluation record
    """
    queryset = PerformanceEvaluation.objects.select_related('emp', 'department', 'manager').all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PerformanceCreateUpdateSerializer
        return PerformanceEvaluationSerializer


class PerformanceDetailView(generics.RetrieveAPIView):
    """
    Retrieve a specific employee performance record.
    """
    queryset = PerformanceEvaluation.objects.select_related('emp', 'department', 'manager').all()
    serializer_class = PerformanceEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]


# -----------------------------
# Summary View (Top/Weak Performers)
# -----------------------------
class PerformanceSummaryView(APIView):
    """
    Returns Top 3 and Weak 3 performers based on total_score.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Get latest evaluation for each employee
        latest_per_emp = (
            PerformanceEvaluation.objects
            .order_by('emp', '-review_date', '-created_at')
            .distinct('emp')
            .select_related('emp', 'department')
        )

        # Sort by total_score
        all_sorted = sorted(latest_per_emp, key=lambda x: x.total_score, reverse=True)

        # Extract Top 3 and Weak 3
        top_3 = all_sorted[:3]
        weak_3 = all_sorted[-3:] if len(all_sorted) > 3 else all_sorted

        def format_data(obj):
            emp = obj.emp
            return {
                "emp_id": getattr(emp, 'emp_id', emp.username),
                "name": f"{emp.first_name} {emp.last_name}".strip(),
                "department": getattr(obj.department, 'name', 'N/A') if obj.department else 'N/A',
                "total_score": obj.total_score,
                "review_date": obj.review_date
            }

        data = {
            "top_performers": [format_data(e) for e in top_3],
            "weak_performers": [format_data(e) for e in weak_3]
        }
        return Response(data, status=status.HTTP_200_OK)
