# ===============================================
# notifications/views.py 
# ===============================================

from rest_framework import generics, status, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from datetime import timedelta
import logging

from .models import Notification
from .serializers import (
    NotificationSerializer,
    NotificationListSerializer,
    NotificationMarkReadSerializer,
    NotificationCreateSerializer,
)

logger = logging.getLogger(__name__)


# ===============================================================
# Pagination (Frontend Friendly)
# ===============================================================
class NotificationPagination(PageNumberPagination):
    """
    Pagination configuration for notification lists.
    Supports dynamic page sizes for different use cases.
    """
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100
    
    def get_paginated_response(self, data):
        """Custom paginated response with metadata."""
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "page_size": self.page_size,
            "total_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "results": data,
        })


# ===============================================================
# Notification List View (All Roles)
# ===============================================================
class NotificationListView(generics.ListAPIView):
    """
    Fetch notifications for the logged-in user.

    Query Parameters:
      - status: unread|read|all (default: all)
      - priority: urgent|high|medium|low
      - category: performance|feedback|system|attendance|leave|announcement
      - auto_delete: true|false
      - expired: true|false (default: false - exclude expired)
      - date_from: YYYY-MM-DD (filter from date)
      - date_to: YYYY-MM-DD (filter to date)
      - search: search in message text
      - ordering: created_at|-created_at|priority|-priority (default: -priority,-created_at)
      
    Pagination:
      - page: page number
      - page_size: items per page (max 100)
      
    Response includes:
      - Paginated notification list
      - Metadata (unread count, priority breakdown)
    """
    serializer_class = NotificationListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["message"]
    ordering_fields = ["created_at", "priority", "is_read"]
    ordering = ["-priority", "-created_at"]  # Urgent first, then newest

    def get_queryset(self):
        """Build filtered queryset based on query parameters."""
        user = self.request.user
        
        # Base queryset with optimizations
        qs = Notification.objects.filter(employee=user).select_related(
            "department", "employee"
        )
        
        # Status filter
        status_filter = self.request.query_params.get("status", "all").lower()
        if status_filter == "unread":
            qs = qs.filter(is_read=False)
        elif status_filter == "read":
            qs = qs.filter(is_read=True)
        
        # Priority filter
        priority = self.request.query_params.get("priority")
        if priority and priority in dict(Notification.PRIORITY_CHOICES):
            qs = qs.filter(priority=priority)
        
        # Category filter
        category = self.request.query_params.get("category")
        if category and category in dict(Notification.CATEGORY_CHOICES):
            qs = qs.filter(category=category)
        
        # Auto-delete filter
        auto_delete = self.request.query_params.get("auto_delete")
        if auto_delete:
            qs = qs.filter(auto_delete=auto_delete.lower() == "true")
        
        # Expiration filter (exclude expired by default)
        include_expired = self.request.query_params.get("expired", "false").lower()
        if include_expired != "true":
            qs = qs.not_expired()
        
        # Date range filters
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        
        if date_from:
            try:
                from_date = timezone.datetime.strptime(date_from, "%Y-%m-%d")
                qs = qs.filter(created_at__gte=from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = timezone.datetime.strptime(date_to, "%Y-%m-%d")
                # Include the entire day
                to_date = to_date + timedelta(days=1)
                qs = qs.filter(created_at__lt=to_date)
            except ValueError:
                pass
        
        return qs

    def list(self, request, *args, **kwargs):
        """Override list to include metadata."""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            
            # Add metadata to response
            metadata = self._get_metadata(request.user)
            response.data["metadata"] = metadata
            
            return response
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _get_metadata(self, user):
        """Get notification metadata for the user."""
        # Try to get from cache first
        cache_key = f"notification_metadata_{user.id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data
        
        # Calculate fresh metadata
        all_notifications = Notification.objects.filter(employee=user).not_expired()
        
        metadata = {
            "total_count": all_notifications.count(),
            "unread_count": all_notifications.filter(is_read=False).count(),
            "priority_breakdown": {
                "urgent": all_notifications.filter(
                    priority=Notification.PRIORITY_URGENT
                ).count(),
                "high": all_notifications.filter(
                    priority=Notification.PRIORITY_HIGH
                ).count(),
                "medium": all_notifications.filter(
                    priority=Notification.PRIORITY_MEDIUM
                ).count(),
                "low": all_notifications.filter(
                    priority=Notification.PRIORITY_LOW
                ).count(),
            },
            "category_breakdown": {
                category[0]: all_notifications.filter(category=category[0]).count()
                for category in Notification.CATEGORY_CHOICES
            },
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, metadata, 300)
        
        return metadata


# ===============================================================
# Notification Detail View
# ===============================================================
class NotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a single notification.
    
    GET: Retrieve notification details (full serializer)
    PATCH: Update notification (e.g., mark as read)
    DELETE: Delete notification
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def get_queryset(self):
        """Only allow access to user's own notifications."""
        return Notification.objects.filter(
            employee=self.request.user
        ).select_related("department", "employee")

    def perform_update(self, serializer):
        """Clear cache when notification is updated."""
        serializer.save()
        self._clear_user_cache()

    def perform_destroy(self, instance):
        """Clear cache when notification is deleted."""
        instance.delete()
        self._clear_user_cache()

    def _clear_user_cache(self):
        """Clear notification-related cache for user."""
        cache_key = f"notification_metadata_{self.request.user.id}"
        cache.delete(cache_key)
        
        count_cache_key = f"unread_count_{self.request.user.id}"
        cache.delete(count_cache_key)


# ===============================================================
# Unread Count View (Bell Icon Endpoint)
# ===============================================================
class UnreadCountView(APIView):
    """
    Return the unread notification count for the logged-in user.
    Cached for 60 seconds to reduce database load.
    
    Response:
    {
        "unread_count": 5,
        "urgent_unread_count": 2
    }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get unread notification count with caching."""
        user = request.user
        cache_key = f"unread_count_{user.id}"
        
        # Try cache first
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)
        
        # Calculate fresh counts
        base_qs = Notification.objects.filter(
            employee=user, 
            is_read=False
        ).not_expired()
        
        data = {
            "unread_count": base_qs.count(),
            "urgent_unread_count": base_qs.filter(
                priority=Notification.PRIORITY_URGENT
            ).count(),
        }
        
        # Cache for 60 seconds
        cache.set(cache_key, data, 60)
        
        return Response(data, status=status.HTTP_200_OK)


# ===============================================================
# Mark Single Notification as Read
# ===============================================================
class MarkNotificationReadView(generics.GenericAPIView):
    """
    Mark a single notification as read.
    Auto-deletes if notification has auto_delete=True.
    
    PATCH /notifications/{id}/mark-read/
    
    Response:
    {
        "message": "Notification marked as read.",
        "notification_id": 123,
        "auto_deleted": false
    }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def patch(self, request, pk):
        """Mark notification as read."""
        notification = get_object_or_404(
            Notification,
            pk=pk,
            employee=request.user
        )

        if notification.is_read:
            return Response(
                {
                    "message": "Notification already marked as read.",
                    "notification_id": pk,
                    "auto_deleted": False,
                },
                status=status.HTTP_200_OK,
            )

        auto_delete = notification.auto_delete
        notification.mark_as_read(auto_commit=True)
        
        # Clear cache
        self._clear_cache(request.user)

        return Response(
            {
                "message": "Notification marked as read and auto-deleted." 
                          if auto_delete else "Notification marked as read.",
                "notification_id": pk,
                "auto_deleted": auto_delete,
            },
            status=status.HTTP_200_OK,
        )

    def _clear_cache(self, user):
        """Clear notification cache for user."""
        cache.delete(f"unread_count_{user.id}")
        cache.delete(f"notification_metadata_{user.id}")


# ===============================================================
# Mark Notification as Unread (Revert)
# ===============================================================
class MarkNotificationUnreadView(generics.GenericAPIView):
    """
    Revert a notification to unread status.
    Only works for persistent (auto_delete=False) notifications.
    
    PATCH /notifications/{id}/mark-unread/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def patch(self, request, pk):
        """Mark notification as unread."""
        notification = get_object_or_404(
            Notification,
            pk=pk,
            employee=request.user
        )

        if notification.auto_delete:
            return Response(
                {"error": "Cannot mark auto-delete notifications as unread."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not notification.is_read:
            return Response(
                {"message": "Notification is already unread."},
                status=status.HTTP_200_OK,
            )

        notification.mark_as_unread(auto_commit=True)
        
        # Clear cache
        cache.delete(f"unread_count_{request.user.id}")
        cache.delete(f"notification_metadata_{request.user.id}")

        return Response(
            {
                "message": "Notification marked as unread.",
                "notification_id": pk,
            },
            status=status.HTTP_200_OK,
        )


# ===============================================================
# Mark All/Multiple Notifications as Read (Bulk)
# ===============================================================
class BulkMarkReadView(generics.GenericAPIView):
    """
    Mark multiple or all notifications as read.
    
    POST /notifications/bulk-mark-read/
    
    Body (optional):
    {
        "notification_ids": [1, 2, 3]  // If empty or not provided, marks all
    }
    
    Response:
    {
        "message": "...",
        "marked_read": 3,
        "auto_deleted": 2,
        "total_processed": 5
    }
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationMarkReadSerializer

    @transaction.atomic
    def post(self, request):
        """Bulk mark notifications as read."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        notification_ids = serializer.validated_data.get("notification_ids", [])
        user = request.user
        
        # Build queryset
        if notification_ids:
            unread_qs = Notification.objects.filter(
                employee=user,
                id__in=notification_ids,
                is_read=False
            )
        else:
            unread_qs = Notification.objects.filter(
                employee=user,
                is_read=False
            ).not_expired()
        
        total_unread = unread_qs.count()
        
        if not total_unread:
            return Response(
                {"message": "No unread notifications to process."},
                status=status.HTTP_200_OK
            )
        
        # Separate auto-delete from persistent
        auto_delete_qs = unread_qs.filter(auto_delete=True)
        persistent_qs = unread_qs.filter(auto_delete=False)
        
        auto_deleted_count = auto_delete_qs.count()
        persistent_count = persistent_qs.count()
        
        # Update persistent notifications
        if persistent_count:
            persistent_qs.update(is_read=True, read_at=timezone.now())
        
        # Delete auto-delete notifications
        if auto_deleted_count:
            auto_delete_qs.delete()
        
        # Clear cache
        cache.delete(f"unread_count_{user.id}")
        cache.delete(f"notification_metadata_{user.id}")
        
        logger.info(
            f"Bulk mark read: User {user.username} - "
            f"marked {persistent_count} persistent, "
            f"deleted {auto_deleted_count} auto-delete notifications"
        )
        
        return Response(
            {
                "message": f"Processed {total_unread} notifications.",
                "marked_read": persistent_count,
                "auto_deleted": auto_deleted_count,
                "total_processed": total_unread,
            },
            status=status.HTTP_200_OK,
        )


# ===============================================================
# Bulk Delete Notifications
# ===============================================================
class BulkDeleteView(generics.GenericAPIView):
    """
    Bulk delete multiple notifications.
    
    POST /notifications/bulk-delete/
    
    Body:
    {
        "notification_ids": [1, 2, 3]
    }
    
    Response:
    {
        "message": "Deleted 3 notifications.",
        "deleted_count": 3
    }
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """Bulk delete notifications."""
        notification_ids = request.data.get("notification_ids", [])
        
        if not notification_ids:
            raise ValidationError({"notification_ids": "This field is required."})
        
        if not isinstance(notification_ids, list):
            raise ValidationError({"notification_ids": "Must be a list of IDs."})
        
        # Only delete user's own notifications
        deleted_count, _ = Notification.objects.filter(
            employee=request.user,
            id__in=notification_ids
        ).delete()
        
        # Clear cache
        cache.delete(f"unread_count_{request.user.id}")
        cache.delete(f"notification_metadata_{request.user.id}")
        
        logger.info(f"Bulk delete: User {request.user.username} deleted {deleted_count} notifications")
        
        return Response(
            {
                "message": f"Deleted {deleted_count} notification(s).",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )


# ===============================================================
# Delete Single Notification
# ===============================================================
class NotificationDeleteView(generics.DestroyAPIView):
    """
    Delete a single notification manually.
    
    DELETE /notifications/{id}/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    lookup_field = "pk"

    def get_queryset(self):
        """Only allow users to delete their own notifications."""
        return Notification.objects.filter(employee=self.request.user)

    def perform_destroy(self, instance):
        """Delete notification and clear cache."""
        instance.delete()
        
        # Clear cache
        cache.delete(f"unread_count_{self.request.user.id}")
        cache.delete(f"notification_metadata_{self.request.user.id}")
        
        logger.info(f"Deleted notification {instance.id} for user {self.request.user.username}")


# ===============================================================
# Cleanup Expired Notifications (Admin Only)
# ===============================================================
class CleanupExpiredNotificationsView(generics.GenericAPIView):
    """
    Admin endpoint to clean up expired notifications.
    
    POST /notifications/admin/cleanup-expired/
    
    Response:
    {
        "message": "Cleaned up 42 expired notifications.",
        "deleted_count": 42
    }
    """
    permission_classes = [IsAdminUser]

    @transaction.atomic
    def post(self, request):
        """Clean up expired notifications."""
        deleted_count = Notification.objects.cleanup_expired()
        
        logger.info(f"Admin cleanup: Deleted {deleted_count} expired notifications")
        
        return Response(
            {
                "message": f"Cleaned up {deleted_count} expired notification(s).",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )


# ===============================================================
# Create Notification (Admin/System Only)
# ===============================================================
class NotificationCreateView(generics.CreateAPIView):
    """
    Admin endpoint to create notifications for users.
    
    POST /notifications/admin/create/
    
    Body:
    {
        "employee_id": 1,
        "message": "Your weekly report is ready",
        "category": "performance",
        "priority": "high",
        "link": "/reports/weekly/",
        "auto_delete": false,
        "expires_at": "2025-11-10T00:00:00Z"
    }
    """
    serializer_class = NotificationCreateSerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        """Create notification and clear cache."""
        notification = serializer.save()
        
        # Clear cache for the recipient
        cache.delete(f"unread_count_{notification.employee.id}")
        cache.delete(f"notification_metadata_{notification.employee.id}")
        
        logger.info(
            f"Admin created notification for user {notification.employee.username}: "
            f"{notification.message[:50]}"
        )


# ===============================================================
# Notification Statistics (Admin)
# ===============================================================
class NotificationStatisticsView(generics.GenericAPIView):
    """
    Admin endpoint for notification statistics.
    
    GET /notifications/admin/statistics/
    
    Query Parameters:
    - date_from: YYYY-MM-DD
    - date_to: YYYY-MM-DD
    
    Response includes:
    - Total notifications
    - Read/Unread breakdown
    - Priority breakdown
    - Category breakdown
    - Average read time
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        """Get notification statistics."""
        # Date range filter
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        
        qs = Notification.objects.all()
        
        if date_from:
            try:
                from_date = timezone.datetime.strptime(date_from, "%Y-%m-%d")
                qs = qs.filter(created_at__gte=from_date)
            except ValueError:
                pass
        
        if date_to:
            try:
                to_date = timezone.datetime.strptime(date_to, "%Y-%m-%d")
                to_date = to_date + timedelta(days=1)
                qs = qs.filter(created_at__lt=to_date)
            except ValueError:
                pass
        
        # Calculate statistics
        total = qs.count()
        read = qs.filter(is_read=True).count()
        unread = qs.filter(is_read=False).count()
        expired = qs.expired().count()
        
        # Priority breakdown
        priority_stats = {
            priority[0]: qs.filter(priority=priority[0]).count()
            for priority in Notification.PRIORITY_CHOICES
        }
        
        # Category breakdown
        category_stats = {
            category[0]: qs.filter(category=category[0]).count()
            for category in Notification.CATEGORY_CHOICES
        }
        
        # Calculate average read time (in hours)
        read_notifications = qs.filter(is_read=True, read_at__isnull=False)
        if read_notifications.exists():
            total_read_time = sum(
                (n.read_at - n.created_at).total_seconds() / 3600
                for n in read_notifications
            )
            avg_read_time_hours = total_read_time / read_notifications.count()
        else:
            avg_read_time_hours = 0
        
        return Response({
            "total_notifications": total,
            "read_notifications": read,
            "unread_notifications": unread,
            "expired_notifications": expired,
            "read_rate": round((read / total * 100) if total > 0 else 0, 2),
            "priority_breakdown": priority_stats,
            "category_breakdown": category_stats,
            "average_read_time_hours": round(avg_read_time_hours, 2),
        })


# ===========================================================
# Helper Functions for Cross-Module Use
# ===========================================================

def create_notification(
    employee,
    message,
    category=Notification.CATEGORY_SYSTEM,
    priority=Notification.PRIORITY_MEDIUM,
    link=None,
    auto_delete=True,
    department=None,
    expires_at=None,
    metadata=None,
):
    """
    Create a notification for an employee.
    
    Args:
        employee: User instance
        message: Notification message
        category: Notification category (use Notification.CATEGORY_* constants)
        priority: Notification priority (use Notification.PRIORITY_* constants)
        link: Optional URL/route link
        auto_delete: Whether to auto-delete after reading
        department: Optional department instance
        expires_at: Optional expiration datetime
        metadata: Optional metadata dict
    
    Returns:
        Notification instance
    
    Example:
        from notifications.views import create_notification
        from notifications.models import Notification
        
        create_notification(
            employee=user,
            message="Your weekly report is ready",
            category=Notification.CATEGORY_PERFORMANCE,
            priority=Notification.PRIORITY_HIGH,
            link="/reports/weekly/?week=44",
            auto_delete=False,
        )
    """
    try:
        notification = Notification.objects.create(
            employee=employee,
            message=message,
            category=category,
            priority=priority,
            link=link,
            auto_delete=auto_delete,
            department=department,
            expires_at=expires_at,
            metadata=metadata or {},
        )
        
        # Clear cache for user
        cache.delete(f"unread_count_{employee.id}")
        cache.delete(f"notification_metadata_{employee.id}")
        
        logger.info(
            f"Created notification for {employee.username}: "
            f"{message[:50]} (priority: {priority})"
        )
        
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create notification for {employee.username}: {e}")
        raise


def create_report_notification(triggered_by, report_type, link, message, department=None):
    """
    Legacy helper function for report notifications.
    Maintained for backward compatibility.
    
    Args:
        triggered_by: User who triggered the report
        report_type: Type of report (for logging)
        link: URL to the report
        message: Notification message
        department: Optional department instance
    
    Returns:
        Notification instance or None
    """
    try:
        return create_notification(
            employee=triggered_by,
            message=message,
            category=Notification.CATEGORY_PERFORMANCE,
            priority=Notification.PRIORITY_MEDIUM,
            link=link,
            auto_delete=False,
            department=department,
        )
    except Exception as e:
        logger.error(f"Failed to create report notification: {e}")
        return None


def create_department_notifications(
    department,
    message,
    category=Notification.CATEGORY_ANNOUNCEMENT,
    priority=Notification.PRIORITY_MEDIUM,
    link=None,
    auto_delete=True,
    expires_at=None,
):
    """
    Create notifications for all active employees in a department.
    
    Args:
        department: Department instance
        message: Notification message
        category: Notification category
        priority: Notification priority
        link: Optional URL/route link
        auto_delete: Whether to auto-delete after reading
        expires_at: Optional expiration datetime
    
    Returns:
        List of created Notification instances
    
    Example:
        from notifications.views import create_department_notifications
        from notifications.models import Notification
        
        create_department_notifications(
            department=dept,
            message="Department meeting tomorrow at 10 AM",
            category=Notification.CATEGORY_ANNOUNCEMENT,
            priority=Notification.PRIORITY_HIGH,
        )
    """
    try:
        notifications = Notification.objects.create_for_department(
            department=department,
            message=message,
            category=category,
            priority=priority,
            link=link,
            auto_delete=auto_delete,
            expires_at=expires_at,
        )
        
        # Clear cache for all affected users
        for notification in notifications:
            cache.delete(f"unread_count_{notification.employee.id}")
            cache.delete(f"notification_metadata_{notification.employee.id}")
        
        logger.info(
            f"Created {len(notifications)} department notifications "
            f"for {department.name}"
        )
        
        return notifications
        
    except Exception as e:
        logger.error(f"Failed to create department notifications: {e}")
        return []