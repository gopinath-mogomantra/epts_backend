# ===============================================
# notifications/views.py 
# ===============================================

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from .models import Notification
from .serializers import NotificationSerializer


# ===============================================================
# Pagination (Frontend Friendly)
# ===============================================================
class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# ===============================================================
# Notification List View (All Roles)
# ===============================================================
class NotificationListView(generics.ListAPIView):
    """
    Fetch notifications for the logged-in user.

    Query Params:
      - ?status=unread|read|all        (default: unread)
      - ?auto_delete=true|false        (optional)
      - Pagination: ?page=1&page_size=10
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        user = self.request.user
        status_filter = self.request.query_params.get("status", "unread").lower()
        auto_delete_filter = self.request.query_params.get("auto_delete")

        qs = Notification.objects.filter(employee=user).select_related("department")

        # Apply status filter
        if status_filter == "unread":
            qs = qs.filter(is_read=False)
        elif status_filter == "read":
            qs = qs.filter(is_read=True)
        elif status_filter != "all":
            qs = qs.filter(is_read=False)

        # Apply optional auto-delete filter
        if auto_delete_filter:
            if auto_delete_filter.lower() == "true":
                qs = qs.filter(auto_delete=True)
            elif auto_delete_filter.lower() == "false":
                qs = qs.filter(auto_delete=False)

        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginated = self.paginate_queryset(queryset)
        serializer = self.get_serializer(paginated, many=True)
        unread_count = Notification.objects.filter(employee=request.user, is_read=False).count()

        return self.get_paginated_response({
            "total_notifications": queryset.count(),
            "unread_count": unread_count,
            "notifications": serializer.data,
        })


# ===============================================================
# Unread Count View (Bell Icon Endpoint)
# ===============================================================
class UnreadCountView(generics.GenericAPIView):
    """Return the unread notification count for the logged-in user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(employee=request.user, is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)


# ===============================================================
# Mark Single Notification as Read
# ===============================================================
class MarkNotificationReadView(generics.GenericAPIView):
    """Marks a single notification as read, with optional auto-delete."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)

        if notification.employee != request.user and not request.user.is_staff:
            raise PermissionDenied("You are not authorized to modify this notification.")

        notification.mark_as_read(auto_commit=True)

        if notification.auto_delete:
            return Response(
                {"message": "Notification marked as read and auto-deleted.", "notification_id": pk},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"message": "Notification marked as read.", "notification_id": pk},
            status=status.HTTP_200_OK,
        )


# ===============================================================
# Mark Notification as Unread (Revert)
# ===============================================================
class MarkNotificationUnreadView(generics.GenericAPIView):
    """Reverts a persistent notification to unread."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)

        if notification.employee != request.user and not request.user.is_staff:
            raise PermissionDenied("You are not authorized to modify this notification.")

        if notification.auto_delete:
            return Response(
                {"error": "Cannot mark auto-delete notifications as unread."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification.mark_as_unread()
        return Response(
            {"message": "Notification marked as unread.", "notification_id": pk},
            status=status.HTTP_200_OK,
        )


# ===============================================================
# Mark All Notifications as Read (Bulk)
# ===============================================================
class MarkAllNotificationsReadView(generics.GenericAPIView):
    """Marks all unread notifications for a user as read."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request):
        user = request.user
        unread_qs = Notification.objects.filter(employee=user, is_read=False)

        total_unread = unread_qs.count()
        if not total_unread:
            return Response({"message": "No unread notifications."}, status=status.HTTP_200_OK)

        auto_delete_qs = unread_qs.filter(auto_delete=True)
        persistent_qs = unread_qs.filter(auto_delete=False)

        auto_deleted_count = auto_delete_qs.count()
        persistent_updated_count = persistent_qs.update(is_read=True, read_at=timezone.now())

        if auto_deleted_count:
            auto_delete_qs.delete()

        return Response({
            "message": (
                f"Marked {persistent_updated_count} notifications as read and "
                f"auto-deleted {auto_deleted_count} temporary notifications."
            ),
            "total_processed": persistent_updated_count + auto_deleted_count,
        }, status=status.HTTP_200_OK)


# ===============================================================
# Delete Notification (Single)
# ===============================================================
class NotificationDeleteView(generics.DestroyAPIView):
    """Delete a single notification manually (Admin or Owner)."""
    permission_classes = [IsAuthenticated]
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    lookup_field = "pk"

    def destroy(self, request, *args, **kwargs):
        notification = self.get_object()

        if notification.employee != request.user and not request.user.is_staff:
            raise PermissionDenied("You are not authorized to delete this notification.")

        notification.delete()
        return Response({"message": "Notification deleted successfully."}, status=status.HTTP_204_NO_CONTENT)



# ===========================================================
# Inline Helper: Report Notification Generator
# ===========================================================
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

def create_report_notification(triggered_by, report_type, link, message, department=None):
    """Creates a notification entry for reports, used by reports module."""
    from .models import Notification  # local import to avoid circular dependency

    try:
        Notification.objects.create(
            employee=triggered_by,
            message=message,
            category="report",
            link=link,
            auto_delete=False,
            department=department,
        )

        logger.info(
            f"Report notification created for "
            f"{getattr(triggered_by, 'emp_id', triggered_by.username)}: {report_type}"
        )
        print(f"Notification: {message}")

    except Exception as e:
        logger.error(f"Failed to create report notification: {e}")
