# ===========================================================
# feedback/views.py
# ===========================================================
"""
Enhanced feedback views with comprehensive features:
- List and detail views with proper serializers
- Acknowledgment and action completion endpoints
- Statistics endpoints
- Advanced filtering
- Permission handling
"""

from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q, Avg, Count
from django.core.cache import cache
from django.utils import timezone
import logging

from employee.models import Employee, Department
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from .serializers import (
    # General Feedback
    GeneralFeedbackSerializer,
    GeneralFeedbackListSerializer,
    
    # Manager Feedback
    ManagerFeedbackSerializer,
    ManagerFeedbackListSerializer,
    
    # Client Feedback
    ClientFeedbackSerializer,
    ClientFeedbackListSerializer,
    
    # Actions
    FeedbackAcknowledgmentSerializer,
    FeedbackActionSerializer,
    FeedbackStatisticsSerializer,
)
from .permissions import IsAdminOrManager, IsCreatorOrAdmin

logger = logging.getLogger(__name__)


# ===========================================================
# Helper Functions
# ===========================================================
def is_admin(user):
    """Check if user is admin."""
    return user.is_superuser or getattr(user, "role", "") == "Admin"


def is_manager(user):
    """Check if user is manager."""
    return getattr(user, "role", "") == "Manager"


def is_employee(user):
    """Check if user is employee."""
    return getattr(user, "role", "") == "Employee"


def clear_feedback_cache(employee_id):
    """Clear cached feedback data for employee."""
    cache_keys = [
        f"feedback_stats_{employee_id}",
        f"feedback_summary_{employee_id}",
    ]
    for key in cache_keys:
        cache.delete(key)


# ===========================================================
# Base Feedback ViewSet (Common functionality)
# ===========================================================
class BaseFeedbackViewSet(viewsets.ModelViewSet):
    """
    Base viewset with common functionality for all feedback types.
    """
    
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["created_at", "rating", "priority", "feedback_date"]
    ordering = ["-priority", "-feedback_date", "-created_at"]
    
    # Subclasses should define these
    list_serializer_class = None
    detail_serializer_class = None
    
    def get_serializer_class(self):
        """Use different serializers for list vs detail views."""
        if self.action == 'list':
            return self.list_serializer_class or self.serializer_class
        return self.detail_serializer_class or self.serializer_class
    
    def get_queryset(self):
        """
        Filter queryset based on user role.
        Admins: see all
        Managers: see their team's feedback
        Employees: see their own public feedback
        """
        user = self.request.user
        qs = super().get_queryset()
        
        # Optimize queries
        qs = qs.select_related('employee__user', 'department', 'created_by')
        
        # Apply role-based filtering
        if is_admin(user):
            return qs
        elif is_manager(user):
            try:
                manager_emp = Employee.objects.get(user=user)
                return qs.filter(
                    Q(created_by=user) | 
                    Q(employee__manager=manager_emp)
                ).distinct()
            except Employee.DoesNotExist:
                return qs.filter(created_by=user)
        elif is_employee(user):
            return qs.filter(
                employee__user=user,
                visibility='Public'
            )
        
        return qs.none()
    
    def filter_queryset(self, queryset):
        """Apply additional custom filters."""
        queryset = super().filter_queryset(queryset)
        
        # Filter by priority
        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by sentiment
        sentiment = self.request.query_params.get('sentiment')
        if sentiment:
            queryset = queryset.filter(sentiment=sentiment)
        
        # Filter by acknowledgment status
        acknowledged = self.request.query_params.get('acknowledged')
        if acknowledged == 'true':
            queryset = queryset.filter(acknowledged=True)
        elif acknowledged == 'false':
            queryset = queryset.filter(acknowledged=False)
        
        # Filter by action required
        requires_action = self.request.query_params.get('requires_action')
        if requires_action == 'true':
            queryset = queryset.filter(requires_action=True, action_completed=False)
        
        # Filter by rating range
        min_rating = self.request.query_params.get('min_rating')
        max_rating = self.request.query_params.get('max_rating')
        if min_rating:
            queryset = queryset.filter(rating__gte=int(min_rating))
        if max_rating:
            queryset = queryset.filter(rating__lte=int(max_rating))
        
        # Filter by date range
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(feedback_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(feedback_date__lte=date_to)
        
        return queryset
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create feedback with proper user assignment."""
        instance = serializer.save(created_by=self.request.user)
        
        # Clear cache for employee
        if instance.employee and instance.employee.user:
            clear_feedback_cache(instance.employee.user.id)
        
        logger.info(
            f"[{instance.__class__.__name__}] Created by {self.request.user.username} "
            f"for {instance.employee.user.emp_id if instance.employee and instance.employee.user else 'N/A'}"
        )
        
        return instance
    
    @transaction.atomic
    def perform_update(self, serializer):
        """Update feedback and clear cache."""
        instance = serializer.save()
        
        # Clear cache for employee
        if instance.employee and instance.employee.user:
            clear_feedback_cache(instance.employee.user.id)
        
        logger.info(f"[{instance.__class__.__name__}] Updated: {instance.id}")
        
        return instance
    
    @transaction.atomic
    def perform_destroy(self, instance):
        """Delete feedback and clear cache."""
        employee_id = instance.employee.user.id if instance.employee and instance.employee.user else None
        
        instance.delete()
        
        if employee_id:
            clear_feedback_cache(employee_id)
        
        logger.info(f"[{instance.__class__.__name__}] Deleted: {instance.id}")
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def acknowledge(self, request, pk=None):
        """
        Allow employee to acknowledge feedback.
        
        POST /feedback/{type}/{id}/acknowledge/
        Body: {"response": "Optional response text"}
        """
        feedback = self.get_object()
        
        # Only the employee can acknowledge their own feedback
        if not (feedback.employee and feedback.employee.user == request.user):
            return Response(
                {"error": "You can only acknowledge your own feedback."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if feedback.acknowledged:
            return Response(
                {"error": "Feedback already acknowledged."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = FeedbackAcknowledgmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        response_text = serializer.validated_data.get('response')
        feedback.acknowledge(response=response_text)
        
        # Clear cache
        clear_feedback_cache(request.user.id)
        
        return Response({
            "message": "Feedback acknowledged successfully.",
            "acknowledged_at": feedback.acknowledged_at,
            "status": feedback.status
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def complete_action(self, request, pk=None):
        """
        Mark action items as completed.
        
        POST /feedback/{type}/{id}/complete-action/
        Body: {"notes": "Optional completion notes"}
        """
        feedback = self.get_object()
        
        # Only employee or admin/manager can complete actions
        is_employee = feedback.employee and feedback.employee.user == request.user
        is_authorized = is_employee or is_admin(request.user) or is_manager(request.user)
        
        if not is_authorized:
            return Response(
                {"error": "You don't have permission to complete actions for this feedback."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not feedback.requires_action:
            return Response(
                {"error": "This feedback does not require action."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if feedback.action_completed:
            return Response(
                {"error": "Action already completed."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = FeedbackActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Update metadata with completion notes
        notes = serializer.validated_data.get('notes')
        if notes:
            feedback.metadata['completion_notes'] = notes
            feedback.metadata['completed_by'] = request.user.username
        
        feedback.complete_action()
        
        # Clear cache
        if feedback.employee and feedback.employee.user:
            clear_feedback_cache(feedback.employee.user.id)
        
        return Response({
            "message": "Action items completed successfully.",
            "action_completed_at": feedback.action_completed_at,
            "status": feedback.status
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrManager])
    def archive(self, request, pk=None):
        """
        Archive feedback.
        
        POST /feedback/{type}/{id}/archive/
        """
        feedback = self.get_object()
        
        if feedback.status == 'archived':
            return Response(
                {"error": "Feedback already archived."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        feedback.archive()
        
        return Response({
            "message": "Feedback archived successfully.",
            "status": feedback.status
        })


# ===========================================================
# General Feedback ViewSet
# ===========================================================
class GeneralFeedbackViewSet(BaseFeedbackViewSet):
    """
    ViewSet for General Feedback (Admin/HR feedback).
    
    List: GET /api/feedback/general-feedback/
    Create: POST /api/feedback/general-feedback/
    Detail: GET /api/feedback/general-feedback/{id}/
    Update: PUT/PATCH /api/feedback/general-feedback/{id}/
    Delete: DELETE /api/feedback/general-feedback/{id}/
    
    Actions:
    - POST /api/feedback/general-feedback/{id}/acknowledge/
    - POST /api/feedback/general-feedback/{id}/complete-action/
    - POST /api/feedback/general-feedback/{id}/archive/
    """
    
    queryset = GeneralFeedback.objects.all()
    serializer_class = GeneralFeedbackSerializer
    list_serializer_class = GeneralFeedbackListSerializer
    detail_serializer_class = GeneralFeedbackSerializer
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text", "tags"]


# ===========================================================
# Manager Feedback ViewSet
# ===========================================================
class ManagerFeedbackViewSet(BaseFeedbackViewSet):
    """
    ViewSet for Manager Feedback.
    
    Managers can only create feedback for their team members.
    """
    
    queryset = ManagerFeedback.objects.all()
    serializer_class = ManagerFeedbackSerializer
    list_serializer_class = ManagerFeedbackListSerializer
    detail_serializer_class = ManagerFeedbackSerializer
    search_fields = [
        "employee__user__first_name", 
        "employee__user__last_name", 
        "feedback_text", 
        "manager_name",
        "tags"
    ]


# ===========================================================
# Client Feedback ViewSet
# ===========================================================
class ClientFeedbackViewSet(BaseFeedbackViewSet):
    """
    ViewSet for Client Feedback.
    
    All authenticated users can view public client feedback.
    """
    
    queryset = ClientFeedback.objects.all()
    serializer_class = ClientFeedbackSerializer
    list_serializer_class = ClientFeedbackListSerializer
    detail_serializer_class = ClientFeedbackSerializer
    search_fields = [
        "client_name", 
        "employee__user__first_name", 
        "employee__user__last_name",
        "feedback_text",
        "project_name",
        "tags"
    ]
    
    def get_permissions(self):
        """
        More lenient permissions for client feedback.
        Everyone can view public feedback.
        """
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminOrManager()]


# ===========================================================
# My Feedback View (Employee Dashboard)
# ===========================================================
class MyFeedbackView(APIView):
    """
    Employee dashboard view showing all feedback for the logged-in employee.
    
    GET /api/feedback/my-feedback/
    
    Returns:
    - All feedback types for the employee
    - Statistics
    - Unacknowledged feedback
    - Action items
    """
    
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get all feedback for logged-in employee."""
        user = request.user
        
        # Check cache first
        cache_key = f"feedback_summary_{user.id}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)
        
        try:
            employee = Employee.objects.get(user=user)
        except Employee.DoesNotExist:
            return Response(
                {"error": "Employee record not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all feedback types
        general_qs = GeneralFeedback.objects.filter(employee=employee)
        manager_qs = ManagerFeedback.objects.filter(employee=employee)
        client_qs = ClientFeedback.objects.filter(employee=employee, visibility='Public')
        
        # Calculate statistics
        all_feedback = list(general_qs) + list(manager_qs) + list(client_qs)
        total_count = len(all_feedback)
        
        if total_count > 0:
            ratings = [f.rating for f in all_feedback]
            avg_rating = sum(ratings) / len(ratings)
            positive_count = sum(1 for r in ratings if r >= 8)
            negative_count = sum(1 for r in ratings if r < 5)
        else:
            avg_rating = 0
            positive_count = 0
            negative_count = 0
        
        unacknowledged_count = sum(
            1 for f in all_feedback if not f.acknowledged
        )
        
        requires_action_count = sum(
            1 for f in all_feedback if f.requires_action and not f.action_completed
        )
        
        # Build response
        summary = {
            "employee": f"{user.first_name} {user.last_name}".strip() or user.username,
            "emp_id": user.emp_id,
            "total_feedback": total_count,
            "average_rating": round(avg_rating, 2),
            "positive_feedback": positive_count,
            "negative_feedback": negative_count,
            "unacknowledged": unacknowledged_count,
            "requires_action": requires_action_count,
            "breakdown": {
                "general": general_qs.count(),
                "manager": manager_qs.count(),
                "client": client_qs.count(),
            }
        }
        
        # Get recent feedback (last 10)
        recent_general = GeneralFeedbackListSerializer(
            general_qs.order_by('-created_at')[:5], 
            many=True
        ).data
        recent_manager = ManagerFeedbackListSerializer(
            manager_qs.order_by('-created_at')[:5], 
            many=True
        ).data
        recent_client = ClientFeedbackListSerializer(
            client_qs.order_by('-created_at')[:5], 
            many=True
        ).data
        
        response_data = {
            "message": "Feedback summary retrieved successfully.",
            "summary": summary,
            "recent_feedback": {
                "general": recent_general,
                "manager": recent_manager,
                "client": recent_client,
            }
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, response_data, 300)
        
        logger.info(f"Feedback summary fetched for {user.emp_id}")
        
        return Response(response_data)


# ===========================================================
# Feedback Statistics View (Admin/Manager)
# ===========================================================
class FeedbackStatisticsView(APIView):
    """
    Get feedback statistics for reporting.
    
    GET /api/feedback/statistics/
    
    Query Parameters:
    - employee_id: Filter by employee
    - department_id: Filter by department
    - date_from: Start date
    - date_to: End date
    - feedback_type: general|manager|client
    """
    
    permission_classes = [IsAdminOrManager]

    def get(self, request):
        """Get feedback statistics."""
        # Get filters
        employee_id = request.query_params.get('employee_id')
        department_id = request.query_params.get('department_id')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        feedback_type = request.query_params.get('feedback_type')
        
        # Build queryset based on type
        if feedback_type == 'general':
            model = GeneralFeedback
        elif feedback_type == 'manager':
            model = ManagerFeedback
        elif feedback_type == 'client':
            model = ClientFeedback
        else:
            # Aggregate all types
            stats = {
                'general': self._get_model_stats(GeneralFeedback, employee_id, department_id, date_from, date_to),
                'manager': self._get_model_stats(ManagerFeedback, employee_id, department_id, date_from, date_to),
                'client': self._get_model_stats(ClientFeedback, employee_id, department_id, date_from, date_to),
            }
            
            # Calculate totals
            total_stats = {
                'total': sum(s['total'] for s in stats.values()),
                'average_rating': sum(s['average_rating'] * s['total'] for s in stats.values()) / sum(s['total'] for s in stats.values()) if sum(s['total'] for s in stats.values()) > 0 else 0,
                'positive': sum(s['positive'] for s in stats.values()),
                'neutral': sum(s['neutral'] for s in stats.values()),
                'negative': sum(s['negative'] for s in stats.values()),
            }
            
            stats['total'] = total_stats
            
            return Response(stats)
        
        # Get stats for specific type
        stats = self._get_model_stats(model, employee_id, department_id, date_from, date_to)
        
        return Response(stats)
    
    def _get_model_stats(self, model, employee_id=None, department_id=None, date_from=None, date_to=None):
        """Get statistics for a specific model."""
        qs = model.objects.all()
        
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        
        if department_id:
            qs = qs.filter(department_id=department_id)
        
        if date_from:
            qs = qs.filter(feedback_date__gte=date_from)
        
        if date_to:
            qs = qs.filter(feedback_date__lte=date_to)
        
        stats = qs.aggregate(
            total=Count('id'),
            average_rating=Avg('rating'),
            positive=Count('id', filter=Q(rating__gte=8)),
            neutral=Count('id', filter=Q(rating__gte=5, rating__lt=8)),
            negative=Count('id', filter=Q(rating__lt=5)),
            acknowledged_count=Count('id', filter=Q(acknowledged=True)),
            requires_action_count=Count('id', filter=Q(requires_action=True, action_completed=False)),
        )
        
        # Handle None values
        stats['average_rating'] = round(stats['average_rating'] or 0, 2)
        stats['total'] = stats['total'] or 0
        
        return stats