# ===========================================================
# performance/views_reports.py (PRODUCTION-READY VERSION)
# ===========================================================
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
import logging

from .models import PerformanceEvaluation
from employee.models import Employee, Department
from .serializers import PerformanceEvaluationSerializer
from .utils_export import generate_excel_report, generate_pdf_report

logger = logging.getLogger("performance")


# ===========================================================
# Pagination for Reports
# ===========================================================
class PerformanceReportPagination(PageNumberPagination):
    """Custom pagination for performance reports."""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


# ===========================================================
# Weekly / Department / Manager Report (Optimized)
# ===========================================================
class PerformanceReportView(generics.ListAPIView):
    """
    List performance evaluations with filtering and role-based access.
    
    Query Parameters:
        - filter: 'weekly', 'department', or 'manager'
        - value: corresponding value for the filter
        - page: page number
        - page_size: results per page
    
    Role-based filtering:
        - Admin: See all evaluations
        - Manager: See only direct reports
        - Employee: See only own evaluations
    """
    serializer_class = PerformanceEvaluationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = PerformanceReportPagination

    def get_queryset(self):
        """Get queryset with proper optimizations and filters."""
        user = self.request.user
        
        # Optimized query with all required FK relationships
        qs = PerformanceEvaluation.objects.select_related(
            "employee__user",
            "employee__department",
            "employee__manager__user",
            "evaluator",
            "department"
        )

        # Role-based filtering
        if user.role == "Manager":
            qs = qs.filter(employee__manager__user=user)
        elif user.role == "Employee":
            qs = qs.filter(employee__user=user)
        # Admin sees all (no filter)

        # Apply additional filters
        filter_type = self.request.query_params.get("filter", "").lower()
        value = self.request.query_params.get("value")

        if filter_type == "weekly" and value:
            try:
                week = int(value)
                if 1 <= week <= 53:
                    qs = qs.filter(week_number=week)
            except (ValueError, TypeError):
                logger.warning(f"Invalid week number: {value}")
                
        elif filter_type == "department" and value:
            qs = qs.filter(department__code__iexact=value)
            
        elif filter_type == "manager" and value:
            qs = qs.filter(employee__manager__user__emp_id__iexact=value)
        
        # Additional filters
        year = self.request.query_params.get("year")
        if year:
            try:
                qs = qs.filter(year=int(year))
            except (ValueError, TypeError):
                pass

        return qs.order_by("-year", "-week_number", "-average_score")


# ===========================================================
# Excel Export (Memory-Optimized)
# ===========================================================
class PerformanceExcelExportView(generics.GenericAPIView):
    """
    Export performance evaluations to Excel with filtering.
    
    Query Parameters:
        - filter: 'department', 'manager', or 'week'
        - value: corresponding value for the filter
        - year: filter by year
    
    Limits: Max 10,000 records per export to prevent memory issues.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    MAX_EXPORT_SIZE = 10000

    @transaction.atomic
    def get(self, request):
        """Generate Excel export with proper optimization."""
        user = request.user
        
        # Base queryset with all required FKs
        qs = PerformanceEvaluation.objects.select_related(
            "employee__user",
            "employee__department",
            "employee__manager__user",
            "department"
        )
        
        # Role-based filtering
        if user.role == "Manager":
            qs = qs.filter(employee__manager__user=user)
        elif user.role == "Employee":
            qs = qs.filter(employee__user=user)
        
        # Apply filters
        filter_type = request.query_params.get("filter")
        value = request.query_params.get("value")

        if filter_type == "department" and value:
            qs = qs.filter(department__code__iexact=value)
        elif filter_type == "manager" and value:
            qs = qs.filter(employee__manager__user__emp_id__iexact=value)
        elif filter_type == "week" and value:
            try:
                qs = qs.filter(week_number=int(value))
            except (ValueError, TypeError):
                pass
        
        # Year filter
        year = request.query_params.get("year")
        if year:
            try:
                qs = qs.filter(year=int(year))
            except (ValueError, TypeError):
                pass

        # Check export size
        count = qs.count()
        if count > self.MAX_EXPORT_SIZE:
            return Response({
                "error": f"Export too large ({count} records). Maximum allowed: {self.MAX_EXPORT_SIZE}",
                "count": count,
                "max_allowed": self.MAX_EXPORT_SIZE,
                "suggestion": "Please apply more specific filters (department, week, year)."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if count == 0:
            return Response({
                "error": "No records found matching the specified filters."
            }, status=status.HTTP_404_NOT_FOUND)

        # Generate filename
        filename = f"performance_report_{timezone.now().strftime('%Y%m%d_%H%M')}.xlsx"
        
        logger.info(
            f"Excel export initiated by {user.emp_id}: {count} records",
            extra={'user': user.emp_id, 'count': count}
        )
        
        return generate_excel_report(qs, filename)


# ===========================================================
# Individual PDF Report (Employee) with Authorization
# ===========================================================
class EmployeePerformancePDFView(generics.GenericAPIView):
    """
    Generate PDF performance report for a specific employee.
    
    Authorization:
        - Employees: Can view only their own report
        - Managers: Can view direct reports' reports
        - Admin: Can view any employee's report
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def get(self, request, emp_id):
        """Generate PDF report with proper authorization."""
        user = request.user
        
        # Fetch employee with optimized query
        employee = get_object_or_404(
            Employee.objects.select_related(
                'user', 'department', 'manager__user'
            ),
            user__emp_id__iexact=emp_id
        )
        
        # Authorization checks
        if user.role == "Employee":
            # Employees can only view their own reports
            if employee.user != user:
                logger.warning(
                    f"Unauthorized PDF access attempt: {user.emp_id} tried to access {emp_id}"
                )
                return Response({
                    "error": "You can only view your own performance report."
                }, status=status.HTTP_403_FORBIDDEN)
                
        elif user.role == "Manager":
            # Managers can view their direct reports only
            if not (employee.manager and employee.manager.user == user):
                logger.warning(
                    f"Unauthorized PDF access: Manager {user.emp_id} tried to access {emp_id}"
                )
                return Response({
                    "error": "You can only view reports for your direct reports."
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Admin can view all (no check needed)
        
        # Load evaluations with optimization
        evaluations = PerformanceEvaluation.objects.select_related(
            'department', 'evaluator'
        ).filter(
            employee=employee
        ).order_by("-year", "-week_number")
        
        logger.info(
            f"PDF report generated for {emp_id} by {user.emp_id}",
            extra={'target': emp_id, 'requester': user.emp_id}
        )
        
        return generate_pdf_report(employee, evaluations)


# ===========================================================
# Department Summary Statistics (Bonus Feature)
# ===========================================================
class DepartmentPerformanceSummaryView(generics.GenericAPIView):
    """
    Get aggregated performance statistics for a department.
    Returns: avg score, top performers, evaluation count, etc.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, dept_code):
        """Get department performance summary."""
        from django.db.models import Avg, Count, Max, Min
        
        user = request.user
        department = get_object_or_404(Department, code__iexact=dept_code)
        
        # Get time range from params
        year = request.query_params.get('year')
        week = request.query_params.get('week')
        
        qs = PerformanceEvaluation.objects.filter(department=department)
        
        if year:
            try:
                qs = qs.filter(year=int(year))
            except (ValueError, TypeError):
                pass
        
        if week:
            try:
                qs = qs.filter(week_number=int(week))
            except (ValueError, TypeError):
                pass
        
        # Calculate statistics
        stats = qs.aggregate(
            total_evaluations=Count('id'),
            avg_score=Avg('average_score'),
            highest_score=Max('average_score'),
            lowest_score=Min('average_score'),
        )
        
        # Get top 5 performers
        top_performers = qs.select_related(
            'employee__user'
        ).order_by('-average_score')[:5].values(
            'employee__user__emp_id',
            'employee__user__first_name',
            'employee__user__last_name',
            'average_score',
            'rank'
        )
        
        return Response({
            "department": {
                "code": department.code,
                "name": department.name
            },
            "statistics": {
                "total_evaluations": stats['total_evaluations'] or 0,
                "average_score": round(stats['avg_score'], 2) if stats['avg_score'] else 0,
                "highest_score": round(stats['highest_score'], 2) if stats['highest_score'] else 0,
                "lowest_score": round(stats['lowest_score'], 2) if stats['lowest_score'] else 0,
            },
            "top_performers": list(top_performers),
            "filters_applied": {
                "year": year,
                "week": week
            }
        })