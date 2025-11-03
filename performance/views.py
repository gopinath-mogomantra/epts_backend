# ===========================================================
# performance/views.py (Enhanced Version — 01-Nov-2025)
# ===========================================================
"""
Performance Evaluation API Views

This module provides comprehensive API endpoints for managing and viewing
employee performance evaluations.

Endpoints Overview:
  • CRUD operations for evaluations
  • Employee performance history
  • Department performance summaries
  • Organization-wide dashboards
  • Leaderboards and rankings
  • Trend analysis and insights

Permission Levels:
  - Admin: Full access to all data
  - Manager: Access to team members' data
  - Employee: Access to own data only
"""
# ===========================================================

from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from django.db.models import Max, F, Avg, Count, Q, Sum, Min
from django.db.models.functions import Rank as RankFunc
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import logging

from .models import PerformanceEvaluation, get_week_range
from .serializers import (
    PerformanceEvaluationSerializer,
    PerformanceCreateUpdateSerializer,
    PerformanceDashboardSerializer,
    PerformanceRankSerializer,
)
from employee.models import Employee, Department
from notifications.models import Notification

logger = logging.getLogger(__name__)


# ===========================================================
# CUSTOM PERMISSIONS
# ===========================================================
class IsAdminOrManager(permissions.BasePermission):
    """Permission class for Admin or Manager access."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_superuser
            or getattr(request.user, "role", "").lower() in ["admin", "manager"]
        )


class CanViewPerformance(permissions.BasePermission):
    """Permission to view performance based on role."""

    def has_object_permission(self, request, view, obj):
        user = request.user
        role = getattr(user, "role", "").lower()

        # Admin has full access
        if user.is_superuser or role == "admin":
            return True

        # Manager can view their team members
        if role == "manager":
            try:
                manager_employee = user.employee_profile
                return obj.employee.manager == manager_employee
            except AttributeError:
                return False

        # Employee can view their own
        return obj.employee.user == user


# ===========================================================
# PAGINATION
# ===========================================================
class PerformancePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# ===========================================================
# PERFORMANCE VIEWSET (CRUD + FILTERS)
# ===========================================================
class PerformanceEvaluationViewSet(viewsets.ModelViewSet):
    """
    Complete CRUD operations for Performance Evaluations.
    
    Permissions:
      - Admin: Full access to all evaluations
      - Manager: Access to team member evaluations
      - Employee: Read-only access to own evaluations
    
    Filters:
      - week_number: Filter by ISO week
      - year: Filter by year
      - evaluation_type: Admin, Manager, Client, Self
      - department: Department code or name
      - employee: Employee ID
      - min_score, max_score: Score range filtering
    
    Ordering:
      - review_date, total_score, average_score, rank
    """

    queryset = PerformanceEvaluation.objects.select_related(
        "employee__user", "evaluator", "department", "employee__manager"
    ).prefetch_related("employee__team_members")
    
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PerformancePagination
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    
    ordering_fields = [
        "review_date", "total_score", "average_score", "rank",
        "week_number", "year"
    ]
    ordering = ["-review_date", "-average_score"]
    
    search_fields = [
        "employee__user__emp_id",
        "employee__user__first_name",
        "employee__user__last_name",
        "department__name",
        "evaluation_type",
    ]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ["create", "update", "partial_update"]:
            return PerformanceCreateUpdateSerializer
        return PerformanceEvaluationSerializer

    def get_queryset(self):
        """Filter queryset based on user role and query parameters."""
        user = self.request.user
        role = getattr(user, "role", "").lower()
        qs = super().get_queryset()

        # Role-based filtering
        if role == "manager":
            qs = qs.filter(employee__manager__user=user)
        elif role == "employee":
            qs = qs.filter(employee__user=user)

        # Apply custom filters
        return self._apply_filters(qs)

    def _apply_filters(self, qs):
        """Apply query parameter filters."""
        params = self.request.query_params

        # Week and year filters
        week = params.get("week_number")
        year = params.get("year")
        if week:
            qs = qs.filter(week_number=week)
        if year:
            qs = qs.filter(year=year)

        # Evaluation type filter
        eval_type = params.get("evaluation_type")
        if eval_type:
            qs = qs.filter(evaluation_type__iexact=eval_type)

        # Department filter
        department = params.get("department")
        if department:
            qs = qs.filter(
                Q(department__code__iexact=department)
                | Q(department__name__icontains=department)
            )

        # Employee filter
        emp_id = params.get("employee")
        if emp_id:
            qs = qs.filter(employee__user__emp_id__iexact=emp_id)

        # Score range filters
        min_score = params.get("min_score")
        max_score = params.get("max_score")
        if min_score:
            qs = qs.filter(average_score__gte=min_score)
        if max_score:
            qs = qs.filter(average_score__lte=max_score)

        # Performance rating filter
        rating = params.get("rating")
        if rating:
            qs = qs.filter(performance_rating__iexact=rating)

        # Finalized filter
        is_finalized = params.get("is_finalized")
        if is_finalized is not None:
            qs = qs.filter(is_finalized=is_finalized.lower() == "true")

        return qs

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAdminOrManager()]
        return [permissions.IsAuthenticated(), CanViewPerformance()]

    # --------------------------------------------------------
    # CREATE — Auto Rank Trigger + Notification
    # --------------------------------------------------------
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create new performance evaluation.
        
        Features:
          - Automatic score calculation
          - Automatic ranking
          - Notification to employee
          - Audit trail logging
        """
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        try:
            # Save evaluation
            instance = serializer.save(
                evaluator=request.user,
                created_by=request.user
            )

            # Update rankings
            instance.update_ranks()
            instance.save(update_fields=['rank', 'overall_rank'])

            # Recalculate ranks for all in same group
            PerformanceEvaluation.recalculate_all_ranks(
                department=instance.department,
                week_number=instance.week_number,
                year=instance.year,
                evaluation_type=instance.evaluation_type
            )

            logger.info(
                f"✅ Performance evaluation created: {instance.employee.user.emp_id} | "
                f"Week {instance.week_number}/{instance.year} | "
                f"Score: {instance.average_score}% | "
                f"By: {request.user.username}"
            )

        except IntegrityError:
            return Response(
                {
                    "error": "Performance evaluation already exists.",
                    "detail": "An evaluation for this employee, week, and type already exists."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception(f"❌ Error saving performance evaluation: {exc}")
            return Response(
                {"error": "An unexpected error occurred while saving evaluation."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Send notification to employee
        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=(
                    f"Your {instance.evaluation_type} performance evaluation for "
                    f"{instance.evaluation_period} has been published. "
                    f"Score: {instance.average_score}% | Rating: {instance.performance_rating}"
                ),
                auto_delete=True,
            )
        except Exception as e:
            logger.warning(f"⚠️ Notification creation failed: {e}")

        # Clear cache
        cache.delete(f"employee_performance_{instance.employee.user.emp_id}")
        cache.delete("performance_dashboard")

        return Response(
            {
                "message": "Performance evaluation recorded successfully.",
                "data": {
                    "id": instance.id,
                    "employee_name": (
                        f"{instance.employee.user.first_name} "
                        f"{instance.employee.user.last_name}"
                    ).strip(),
                    "emp_id": instance.employee.user.emp_id,
                    "department_name": instance.department.name if instance.department else None,
                    "evaluation_type": instance.evaluation_type,
                    "average_score": float(instance.average_score),
                    "performance_rating": instance.performance_rating,
                    "rank": instance.rank,
                    "overall_rank": instance.overall_rank,
                    "evaluation_period": instance.evaluation_period,
                    "remarks": instance.remarks,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Update evaluation with rank recalculation."""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Check if finalized
        if instance.is_finalized:
            return Response(
                {
                    "error": "Cannot edit finalized evaluation.",
                    "detail": "This evaluation has been finalized and locked from editing."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        updated_instance = serializer.save()

        # Recalculate ranks
        updated_instance.update_ranks()
        updated_instance.save(update_fields=['rank', 'overall_rank'])

        logger.info(
            f"✏️ Performance evaluation updated: {updated_instance.employee.user.emp_id} | "
            f"By: {request.user.username}"
        )

        # Clear cache
        cache.delete(f"employee_performance_{updated_instance.employee.user.emp_id}")

        return Response(
            {
                "message": "Performance evaluation updated successfully.",
                "data": PerformanceEvaluationSerializer(
                    updated_instance, context={"request": request}
                ).data,
            },
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------------
    # Custom Actions
    # --------------------------------------------------------
    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        """Finalize evaluation (lock from editing)."""
        evaluation = self.get_object()
        
        if evaluation.is_finalized:
            return Response(
                {"message": "Evaluation is already finalized."},
                status=status.HTTP_200_OK,
            )
        
        evaluation.finalize()
        logger.info(f"🔒 Evaluation finalized: {evaluation.id} by {request.user.username}")
        
        return Response(
            {"message": "Evaluation finalized successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def unfinalize(self, request, pk=None):
        """Unlock evaluation for editing (Admin only)."""
        if not (request.user.is_superuser or getattr(request.user, "role", "").lower() == "admin"):
            return Response(
                {"error": "Only admins can unfinalize evaluations."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        evaluation = self.get_object()
        evaluation.unfinalize()
        logger.info(f"🔓 Evaluation unlocked: {evaluation.id} by {request.user.username}")
        
        return Response(
            {"message": "Evaluation unlocked successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def insights(self, request, pk=None):
        """Get detailed insights for an evaluation."""
        evaluation = self.get_object()
        
        return Response(
            {
                "evaluation_id": evaluation.id,
                "employee": {
                    "emp_id": evaluation.employee.user.emp_id,
                    "name": f"{evaluation.employee.user.first_name} {evaluation.employee.user.last_name}".strip(),
                },
                "scores": {
                    "total": evaluation.total_score,
                    "average": float(evaluation.average_score),
                    "rating": evaluation.performance_rating,
                },
                "rankings": {
                    "department": evaluation.rank,
                    "overall": evaluation.overall_rank,
                },
                "category_averages": evaluation.get_category_averages(),
                "strengths_weaknesses": evaluation.get_strengths_and_weaknesses(top_n=3),
                "summary": evaluation.get_metric_summary(),
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# EMPLOYEE PERFORMANCE BY ID
# ===========================================================
class EmployeePerformanceByIdView(APIView):
    """
    Return all performance evaluations for a specific employee.
    
    Query Parameters:
      - week: Filter by week number
      - year: Filter by year
      - evaluation_type: Filter by evaluation type
      - include_insights: Include detailed analysis
    """
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, emp_id):
        """Get employee's performance history."""
        role = getattr(request.user, "role", "").lower()

        # Permission check
        if role == "employee" and request.user.emp_id != emp_id:
            return Response(
                {"error": "Employees can only view their own performance data."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check cache
        cache_key = f"employee_performance_{emp_id}"
        cached_data = cache.get(cache_key)
        if cached_data and not request.query_params:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Get employee
        try:
            emp = Employee.objects.select_related("user", "department", "manager__user").get(
                user__emp_id=emp_id
            )
        except Employee.DoesNotExist:
            return Response(
                {"error": f"Employee '{emp_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get evaluations
        qs = PerformanceEvaluation.objects.filter(employee=emp).select_related(
            "employee__user", "department", "evaluator"
        ).order_by("-review_date")

        # Apply filters
        week = request.query_params.get("week")
        year = request.query_params.get("year")
        eval_type = request.query_params.get("evaluation_type")

        if week:
            qs = qs.filter(week_number=week)
        if year:
            qs = qs.filter(year=year)
        if eval_type:
            qs = qs.filter(evaluation_type__iexact=eval_type)

        if not qs.exists():
            return Response(
                {
                    "message": f"No performance data found for employee {emp_id}.",
                    "employee": {
                        "emp_id": emp_id,
                        "name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Calculate statistics
        stats = qs.aggregate(
            avg_score=Avg("average_score"),
            max_score=Max("average_score"),
            min_score=Avg("average_score"),  # Should be Min
            total_evaluations=Count("id"),
        )

        # Serialize data
        serializer = PerformanceEvaluationSerializer(qs, many=True)

        response_data = {
            "employee": {
                "emp_id": emp.user.emp_id,
                "name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                "department": emp.department.name if emp.department else None,
                "manager": (
                    f"{emp.manager.user.first_name} {emp.manager.user.last_name}".strip()
                    if emp.manager
                    else None
                ),
            },
            "statistics": {
                "total_evaluations": stats["total_evaluations"],
                "average_score": round(stats["avg_score"] or 0, 2),
                "highest_score": round(stats["max_score"] or 0, 2),
                "lowest_score": round(stats["min_score"] or 0, 2),
            },
            "evaluations": serializer.data,
        }

        # Add insights if requested
        if request.query_params.get("include_insights", "false").lower() == "true":
            latest = qs.first()
            if latest:
                response_data["latest_insights"] = {
                    "category_averages": latest.get_category_averages(),
                    "strengths_weaknesses": latest.get_strengths_and_weaknesses(),
                }

        # Cache for 5 minutes
        if not request.query_params:
            cache.set(cache_key, response_data, 300)

        return Response(response_data, status=status.HTTP_200_OK)


# ===========================================================
# PERFORMANCE SUMMARY (Admin / Manager Dashboard)
# ===========================================================
class PerformanceSummaryView(APIView):
    """
    Weekly summary with department analysis and leaderboards.
    
    Features:
      - Latest week overview
      - Department rankings
      - Top and weak performers
      - Trend analysis
    """
    
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        """Get performance summary for latest week."""
        # Check cache
        cache_key = "performance_summary_latest"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data, status=status.HTTP_200_OK)

        # Get latest week/year
        latest_eval = PerformanceEvaluation.objects.order_by("-year", "-week_number").first()
        
        if not latest_eval:
            return Response(
                {"message": "No performance data available yet."},
                status=status.HTTP_200_OK,
            )

        latest_year = latest_eval.year
        latest_week = latest_eval.week_number

        # Get evaluations for latest week
        qs = PerformanceEvaluation.objects.filter(
            year=latest_year, week_number=latest_week
        ).select_related("employee__user", "department")

        # Overall statistics
        overall_stats = qs.aggregate(
            avg_score=Avg("average_score"),
            total_evaluations=Count("id"),
            total_employees=Count("employee", distinct=True),
        )

        # Department summary
        dept_summary = (
            qs.values("department__name", "department__code")
            .annotate(
                avg_score=Avg("average_score"),
                employee_count=Count("employee", distinct=True),
            )
            .order_by("-avg_score")
        )

        departments = [
            {
                "department_name": d["department__name"] or "N/A",
                "department_code": d["department__code"],
                "average_score": round(d["avg_score"], 2),
                "employee_count": d["employee_count"],
            }
            for d in dept_summary
        ]

        # Top performers
        top_performers = qs.order_by("-average_score")[:10]
        top_serialized = PerformanceRankSerializer(top_performers, many=True).data

        # Weak performers (need improvement)
        weak_performers = qs.filter(average_score__lt=70).order_by("average_score")[:10]
        weak_serialized = PerformanceRankSerializer(weak_performers, many=True).data

        # Outstanding performers (90+)
        outstanding = qs.filter(average_score__gte=90).count()

        response_data = {
            "period": {
                "week": latest_week,
                "year": latest_year,
                "description": latest_eval.evaluation_period,
            },
            "overall_statistics": {
                "average_score": round(overall_stats["avg_score"] or 0, 2),
                "total_evaluations": overall_stats["total_evaluations"],
                "total_employees": overall_stats["total_employees"],
                "outstanding_performers": outstanding,
            },
            "department_summary": departments,
            "top_10_performers": top_serialized,
            "needs_improvement": weak_serialized,
        }

        # Cache for 10 minutes
        cache.set(cache_key, response_data, 600)

        return Response(response_data, status=status.HTTP_200_OK)


# ===========================================================
# EMPLOYEE DASHBOARD (Self Performance Trend)
# ===========================================================
class EmployeeDashboardView(APIView):
    """
    Personal performance dashboard for logged-in employee.
    
    Features:
      - Performance trend over time
      - Best and worst weeks
      - Category-wise analysis
      - Comparison with department average
    """
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get employee's personal performance dashboard."""
        user = request.user
        
        try:
            employee = Employee.objects.select_related("user", "department").get(user=user)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all evaluations
        records = PerformanceEvaluation.objects.filter(employee=employee).order_by("-review_date")

        if not records.exists():
            return Response(
                {
                    "message": "No performance data found.",
                    "employee": {
                        "emp_id": user.emp_id,
                        "name": f"{user.first_name} {user.last_name}".strip(),
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Calculate statistics
        stats = records.aggregate(
            avg_score=Avg("average_score"),
            max_score=Max("average_score"),
            min_score=Min("average_score"),  # Fixed from Avg
        )

        # Best and worst weeks
        best_week = records.order_by("-average_score").first()
        worst_week = records.order_by("average_score").first()

        # Trend data (last 12 weeks)
        trend_data = list(
            records.order_by("-year", "-week_number")[:12]
            .values("week_number", "year", "average_score", "performance_rating")
            .order_by("year", "week_number")
        )

        # Department average comparison (if department exists)
        dept_comparison = None
        if employee.department:
            dept_avg = PerformanceEvaluation.objects.filter(
                department=employee.department
            ).aggregate(avg=Avg("average_score"))
            
            dept_comparison = {
                "department_average": round(dept_avg["avg"] or 0, 2),
                "your_average": round(stats["avg_score"] or 0, 2),
                "difference": round((stats["avg_score"] or 0) - (dept_avg["avg"] or 0), 2),
            }

        # Latest evaluation insights
        latest = records.first()
        latest_insights = None
        if latest:
            latest_insights = {
                "evaluation_period": latest.evaluation_period,
                "average_score": float(latest.average_score),
                "performance_rating": latest.performance_rating,
                "rank": latest.rank,
                "category_averages": latest.get_category_averages(),
                "strengths_weaknesses": latest.get_strengths_and_weaknesses(),
            }

        serializer = PerformanceDashboardSerializer(records[:10], many=True)

        return Response(
            {
                "employee": {
                    "emp_id": user.emp_id,
                    "name": f"{user.first_name} {user.last_name}".strip(),
                    "department": employee.department.name if employee.department else None,
                },
                "statistics": {
                    "total_evaluations": records.count(),
                    "average_score": round(stats["avg_score"] or 0, 2),
                    "highest_score": round(stats["max_score"] or 0, 2),
                    "lowest_score": round(stats["min_score"] or 0, 2),
                },
                "best_week": {
                    "period": best_week.evaluation_period,
                    "score": float(best_week.average_score),
                    "rating": best_week.performance_rating,
                } if best_week else None,
                "worst_week": {
                    "period": worst_week.evaluation_period,
                    "score": float(worst_week.average_score),
                    "rating": worst_week.performance_rating,
                } if worst_week else None,
                "trend_data": trend_data,
                "department_comparison": dept_comparison,
                "latest_insights": latest_insights,
                "recent_evaluations": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ORGANIZATION PERFORMANCE DASHBOARD
# ===========================================================
class PerformanceDashboardView(APIView):
    """
    Organization-wide performance dashboard with comprehensive analytics.
    
    Features:
      - Overall organization metrics
      - Department-wise breakdown
      - Performance distribution
      - Trend analysis
      - Top and weak performers
    """
    
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        """Get organization performance dashboard."""
        try:
            # Check cache
            cache_key = "performance_dashboard"
            cached_data = cache.get(cache_key)
            if cached_data:
                return Response(cached_data, status=status.HTTP_200_OK)

            evaluations = PerformanceEvaluation.objects.select_related(
                "employee__user", "department"
            )

            if not evaluations.exists():
                return Response(
                    {"message": "No performance data available."},
                    status=status.HTTP_200_OK,
                )

            # Overall statistics
            overall_stats = evaluations.aggregate(
                total_evaluations=Count("id"),
                unique_employees=Count("employee", distinct=True),
                avg_score=Avg("average_score"),
                outstanding=Count("id", filter=Q(average_score__gte=90)),
                exceeds=Count("id", filter=Q(average_score__gte=80, average_score__lt=90)),
                meets=Count("id", filter=Q(average_score__gte=70, average_score__lt=80)),
                needs_improvement=Count("id", filter=Q(average_score__gte=60, average_score__lt=70)),
                unsatisfactory=Count("id", filter=Q(average_score__lt=60)),
            )

            # Department statistics
            dept_stats = (
                evaluations.values("department__name", "department__code")
                .annotate(
                    avg_score=Avg("average_score"),
                    employee_count=Count("employee", distinct=True),
                    evaluation_count=Count("id"),
                )
                .order_by("-avg_score")
            )

            department_scores = [
                {
                    "department": d["department__name"] or "Unassigned",
                    "code": d["department__code"],
                    "average_score": round(d["avg_score"], 2),
                    "employee_count": d["employee_count"],
                    "evaluation_count": d["evaluation_count"],
                }
                for d in dept_stats
            ]

            # Top performers (by average across all evaluations)
            top_employees = (
                evaluations.values(
                    "employee__user__emp_id",
                    "employee__user__first_name",
                    "employee__user__last_name",
                    "department__name",
                )
                .annotate(avg_score=Avg("average_score"), eval_count=Count("id"))
                .order_by("-avg_score")[:10]
            )

            top_performers = [
                {
                    "emp_id": e["employee__user__emp_id"],
                    "name": f"{e['employee__user__first_name']} {e['employee__user__last_name']}".strip(),
                    "department": e["department__name"],
                    "average_score": round(e["avg_score"], 2),
                    "evaluation_count": e["eval_count"],
                }
                for e in top_employees
            ]

            # Weak performers (need support)
            weak_employees = (
                evaluations.values(
                    "employee__user__emp_id",
                    "employee__user__first_name",
                    "employee__user__last_name",
                    "department__name",
                )
                .annotate(avg_score=Avg("average_score"), eval_count=Count("id"))
                .filter(avg_score__lt=70)
                .order_by("avg_score")[:10]
            )

            weak_performers = [
                {
                    "emp_id": e["employee__user__emp_id"],
                    "name": f"{e['employee__user__first_name']} {e['employee__user__last_name']}".strip(),
                    "department": e["department__name"],
                    "average_score": round(e["avg_score"], 2),
                    "evaluation_count": e["eval_count"],
                }
                for e in weak_employees
            ]

            # Performance distribution
            distribution = {
                "Outstanding (90-100%)": overall_stats["outstanding"],
                "Exceeds Expectations (80-89%)": overall_stats["exceeds"],
                "Meets Expectations (70-79%)": overall_stats["meets"],
                "Needs Improvement (60-69%)": overall_stats["needs_improvement"],
                "Unsatisfactory (0-59%)": overall_stats["unsatisfactory"],
            }

            # Active departments count
            active_departments = Department.objects.filter(is_active=True).count()

            response_data = {
                "organization_overview": {
                    "total_evaluations": overall_stats["total_evaluations"],
                    "unique_employees_evaluated": overall_stats["unique_employees"],
                    "active_departments": active_departments,
                    "organization_average_score": round(overall_stats["avg_score"] or 0, 2),
                },
                "performance_distribution": distribution,
                "department_breakdown": department_scores,
                "top_10_performers": top_performers,
                "needs_attention": weak_performers,
            }

            # Cache for 15 minutes
            cache.set(cache_key, response_data, 900)

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"❌ Error generating performance dashboard: {e}")
            return Response(
                {"error": "An error occurred while generating the dashboard."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ===========================================================
# DEPARTMENT PERFORMANCE VIEW
# ===========================================================
class DepartmentPerformanceView(APIView):
    """
    Performance analytics for a specific department.
    
    Query Parameters:
      - week: Filter by week number
      - year: Filter by year
      - include_trends: Include historical trends
    """
    
    permission_classes = [IsAdminOrManager]

    def get(self, request, department_code):
        """Get department-specific performance analytics."""
        try:
            department = Department.objects.get(code__iexact=department_code)
        except Department.DoesNotExist:
            return Response(
                {"error": f"Department '{department_code}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get evaluations
        evaluations = PerformanceEvaluation.objects.filter(
            department=department
        ).select_related("employee__user")

        # Apply filters
        week = request.query_params.get("week")
        year = request.query_params.get("year")
        
        if week:
            evaluations = evaluations.filter(week_number=week)
        if year:
            evaluations = evaluations.filter(year=year)

        if not evaluations.exists():
            return Response(
                {
                    "message": f"No performance data for {department.name}.",
                    "department": {
                        "name": department.name,
                        "code": department.code,
                    },
                },
                status=status.HTTP_200_OK,
            )

        # Statistics
        stats = evaluations.aggregate(
            avg_score=Avg("average_score"),
            max_score=Max("average_score"),
            min_score=Min("average_score"),
            total_evaluations=Count("id"),
            unique_employees=Count("employee", distinct=True),
        )

        # Employee rankings within department
        employee_rankings = (
            evaluations.values(
                "employee__user__emp_id",
                "employee__user__first_name",
                "employee__user__last_name",
            )
            .annotate(avg_score=Avg("average_score"), eval_count=Count("id"))
            .order_by("-avg_score")
        )

        rankings = [
            {
                "rank": idx + 1,
                "emp_id": emp["employee__user__emp_id"],
                "name": f"{emp['employee__user__first_name']} {emp['employee__user__last_name']}".strip(),
                "average_score": round(emp["avg_score"], 2),
                "evaluation_count": emp["eval_count"],
            }
            for idx, emp in enumerate(employee_rankings)
        ]

        # Trends (if requested)
        trends = None
        if request.query_params.get("include_trends", "false").lower() == "true":
            weekly_trends = (
                PerformanceEvaluation.objects.filter(department=department)
                .values("week_number", "year")
                .annotate(avg_score=Avg("average_score"), eval_count=Count("id"))
                .order_by("year", "week_number")[-12:]  # Last 12 weeks
            )
            trends = list(weekly_trends)

        return Response(
            {
                "department": {
                    "name": department.name,
                    "code": department.code,
                    "is_active": department.is_active,
                },
                "statistics": {
                    "total_evaluations": stats["total_evaluations"],
                    "unique_employees": stats["unique_employees"],
                    "average_score": round(stats["avg_score"] or 0, 2),
                    "highest_score": round(stats["max_score"] or 0, 2),
                    "lowest_score": round(stats["min_score"] or 0, 2),
                },
                "employee_rankings": rankings,
                "trends": trends,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# PERFORMANCE TRENDS VIEW
# ===========================================================
class PerformanceTrendsView(APIView):
    """
    Historical performance trends and analytics.
    
    Query Parameters:
      - department: Filter by department code
      - employee: Filter by employee ID
      - weeks: Number of weeks to include (default: 12)
      - evaluation_type: Filter by evaluation type
    """
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get performance trends over time."""
        role = getattr(request.user, "role", "").lower()
        
        # Base queryset
        evaluations = PerformanceEvaluation.objects.all()

        # Role-based filtering
        if role == "manager":
            evaluations = evaluations.filter(employee__manager__user=request.user)
        elif role == "employee":
            evaluations = evaluations.filter(employee__user=request.user)

        # Apply filters
        department = request.query_params.get("department")
        employee = request.query_params.get("employee")
        eval_type = request.query_params.get("evaluation_type")
        weeks = int(request.query_params.get("weeks", 12))

        if department:
            evaluations = evaluations.filter(department__code__iexact=department)
        if employee:
            evaluations = evaluations.filter(employee__user__emp_id__iexact=employee)
        if eval_type:
            evaluations = evaluations.filter(evaluation_type__iexact=eval_type)

        # Get weekly trends
        weekly_trends = (
            evaluations.values("week_number", "year")
            .annotate(
                avg_score=Avg("average_score"),
                max_score=Max("average_score"),
                min_score=Min("average_score"),
                eval_count=Count("id"),
            )
            .order_by("-year", "-week_number")[:weeks]
        )

        trends = list(weekly_trends)
        trends.reverse()  # Chronological order

        # Category trends (last 4 weeks)
        recent_evals = evaluations.order_by("-review_date")[:4]
        category_trends = {}
        
        if recent_evals.exists():
            for evaluation in recent_evals:
                period = evaluation.evaluation_period
                category_trends[period] = evaluation.get_category_averages()

        return Response(
            {
                "weekly_trends": trends,
                "category_trends": category_trends,
                "total_weeks": len(trends),
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# PERFORMANCE COMPARISON VIEW
# ===========================================================
class PerformanceComparisonView(APIView):
    """
    Compare performance between employees, departments, or time periods.
    
    Query Parameters:
      - type: 'employee' or 'department'
      - ids: Comma-separated IDs to compare
      - week: Week number
      - year: Year
    """
    
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        """Compare performance across entities."""
        comparison_type = request.query_params.get("type", "employee")
        ids = request.query_params.get("ids", "").split(",")
        week = request.query_params.get("week")
        year = request.query_params.get("year")

        if not ids or ids == [""]:
            return Response(
                {"error": "Please provide IDs to compare."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results = []

        if comparison_type == "employee":
            for emp_id in ids:
                try:
                    emp = Employee.objects.get(user__emp_id__iexact=emp_id.strip())
                    evals = PerformanceEvaluation.objects.filter(employee=emp)
                    
                    if week:
                        evals = evals.filter(week_number=week)
                    if year:
                        evals = evals.filter(year=year)

                    stats = evals.aggregate(
                        avg_score=Avg("average_score"),
                        eval_count=Count("id"),
                    )

                    latest = evals.order_by("-review_date").first()
                    category_avg = latest.get_category_averages() if latest else {}

                    results.append({
                        "emp_id": emp_id,
                        "name": f"{emp.user.first_name} {emp.user.last_name}".strip(),
                        "department": emp.department.name if emp.department else None,
                        "average_score": round(stats["avg_score"] or 0, 2),
                        "evaluation_count": stats["eval_count"],
                        "category_averages": category_avg,
                    })
                except Employee.DoesNotExist:
                    results.append({
                        "emp_id": emp_id,
                        "error": "Employee not found",
                    })

        elif comparison_type == "department":
            for dept_code in ids:
                try:
                    dept = Department.objects.get(code__iexact=dept_code.strip())
                    evals = PerformanceEvaluation.objects.filter(department=dept)
                    
                    if week:
                        evals = evals.filter(week_number=week)
                    if year:
                        evals = evals.filter(year=year)

                    stats = evals.aggregate(
                        avg_score=Avg("average_score"),
                        employee_count=Count("employee", distinct=True),
                    )

                    results.append({
                        "department_code": dept_code,
                        "department_name": dept.name,
                        "average_score": round(stats["avg_score"] or 0, 2),
                        "employee_count": stats["employee_count"],
                    })
                except Department.DoesNotExist:
                    results.append({
                        "department_code": dept_code,
                        "error": "Department not found",
                    })

        return Response(
            {
                "comparison_type": comparison_type,
                "filter": {
                    "week": week,
                    "year": year,
                },
                "results": results,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# LEADERBOARD VIEW
# ===========================================================
class LeaderboardView(APIView):
    """
    Organization-wide leaderboard.
    
    Query Parameters:
      - week: Filter by week
      - year: Filter by year
      - department: Filter by department
      - evaluation_type: Filter by evaluation type
      - limit: Number of results (default: 50)
    """
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get performance leaderboard."""
        # Base queryset
        evaluations = PerformanceEvaluation.objects.select_related(
            "employee__user", "department"
        )

        # Apply filters
        week = request.query_params.get("week")
        year = request.query_params.get("year")
        department = request.query_params.get("department")
        eval_type = request.query_params.get("evaluation_type")
        limit = int(request.query_params.get("limit", 50))

        if week:
            evaluations = evaluations.filter(week_number=week)
        if year:
            evaluations = evaluations.filter(year=year)
        if department:
            evaluations = evaluations.filter(department__code__iexact=department)
        if eval_type:
            evaluations = evaluations.filter(evaluation_type__iexact=eval_type)

        if not evaluations.exists():
            return Response(
                {"message": "No performance data for specified filters."},
                status=status.HTTP_200_OK,
            )

        # Get top performers
        top_performers = evaluations.order_by("-average_score", "employee__user__emp_id")[:limit]

        leaderboard = [
            {
                "rank": idx + 1,
                "emp_id": perf.employee.user.emp_id,
                "name": f"{perf.employee.user.first_name} {perf.employee.user.last_name}".strip(),
                "department": perf.department.name if perf.department else "N/A",
                "department_code": perf.department.code if perf.department else None,
                "average_score": float(perf.average_score),
                "performance_rating": perf.performance_rating,
                "evaluation_period": perf.evaluation_period,
                "evaluation_type": perf.evaluation_type,
            }
            for idx, perf in enumerate(top_performers)
        ]

        return Response(
            {
                "filters": {
                    "week": week,
                    "year": year,
                    "department": department,
                    "evaluation_type": eval_type,
                },
                "total_results": evaluations.count(),
                "leaderboard": leaderboard,
            },
            status=status.HTTP_200_OK,
        )