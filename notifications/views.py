# ===============================================
# notifications/views.py (Updated — Production Ready)
# ===============================================

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from .models import Notification
from .serializers import NotificationSerializer


# -------------------------------------------------------
# Pagination (frontend-friendly)
# -------------------------------------------------------
class NotificationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


# ===============================================================
# ✅ Notification List View (Unified for All Roles)
# ===============================================================
class NotificationListView(generics.ListAPIView):
    """
    Fetch notifications for the logged-in user.
    Supports query params:
      - ?status=unread | read | all     (default: unread)
      - ?auto_delete=true|false         (optional filter)
      - pagination via ?page and ?page_size
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        user = self.request.user
        status_filter = self.request.query_params.get("status", "unread").lower()
        auto_delete_filter = self.request.query_params.get("auto_delete", None)

        qs = Notification.objects.filter(employee=user).select_related("department")

        # Status filter
        if status_filter == "unread":
            qs = qs.filter(is_read=False)
        elif status_filter == "read":
            qs = qs.filter(is_read=True)
        elif status_filter == "all":
            pass
        else:
            qs = qs.filter(is_read=False)

        # Optional auto-delete filter
        if auto_delete_filter is not None:
            if auto_delete_filter.lower() == "true":
                qs = qs.filter(auto_delete=True)
            elif auto_delete_filter.lower() == "false":
                qs = qs.filter(auto_delete=False)

        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginated = self.paginate_queryset(queryset)
        serializer = self.get_serializer(paginated, many=True)
        # Unread count for the full set (not only the page)
        unread_count = Notification.objects.filter(employee=request.user, is_read=False).count()
        return self.get_paginated_response(
            {
                "total": queryset.count(),
                "unread_count": unread_count,
                "notifications": serializer.data,
            }
        )


# ===============================================================
# ✅ Unread Count (quick endpoint used by header/badges)
# ===============================================================
class UnreadCountView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(employee=request.user, is_read=False).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)


# ===============================================================
# ✅ Mark single notification as read (or auto-delete)
# ===============================================================
class MarkNotificationReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)

        # Ownership check (admins may also operate if deliberately allowed)
        if notification.employee != request.user and not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("You are not authorized to modify this notification.")

        # Use model helper which honors auto_delete behavior
        # mark_as_read will delete if auto_delete is True
        notification.mark_as_read(auto_commit=True)

        # If object was auto-deleted, it will no longer exist in DB
        if notification.auto_delete:
            return Response(
                {"message": "✅ Notification marked as read and auto-deleted.", "notification_id": pk},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "✅ Notification marked as read.", "notification_id": pk},
            status=status.HTTP_200_OK,
        )


# ===============================================================
# ✅ Mark single notification as unread (revert)
# ===============================================================
class MarkNotificationUnreadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)

        if notification.employee != request.user and not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("You are not authorized to modify this notification.")

        # Only persistent notifications can be marked unread (auto-deleted ones would have been removed)
        if notification.auto_delete:
            return Response(
                {"error": "Cannot mark auto-delete notifications as unread."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification.mark_as_unread()
        return Response({"message": "✅ Notification marked as unread.", "notification_id": pk}, status=status.HTTP_200_OK)


# ===============================================================
# ✅ Bulk: Mark all unread notifications as read
# ===============================================================
class MarkAllNotificationsReadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request):
        user = request.user
        unread_qs = Notification.objects.filter(employee=user, is_read=False)

        total_unread = unread_qs.count()
        if total_unread == 0:
            return Response({"message": "No unread notifications."}, status=status.HTTP_200_OK)

        # Separate auto-delete ones (delete) and persistent ones (bulk update)
        auto_delete_qs = unread_qs.filter(auto_delete=True)
        persistent_qs = unread_qs.filter(auto_delete=False)

        auto_deleted_count = auto_delete_qs.count()
        persistent_updated_count = persistent_qs.update(is_read=True, read_at=timezone.now())

        # Delete auto-delete notifications in a single operation
        if auto_delete_qs.exists():
            auto_delete_qs.delete()

        return Response(
            {
                "message": f"✅ Marked {persistent_updated_count} notifications as read and auto-deleted {auto_deleted_count} temporary notifications.",
                "total_processed": persistent_updated_count + auto_deleted_count,
            },
            status=status.HTTP_200_OK,
        )


# ===============================================================
# ✅ Delete a single notification (owner or admin)
# ===============================================================
class NotificationDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    lookup_field = "pk"

    def destroy(self, request, *args, **kwargs):
        notification = self.get_object()

        if notification.employee != request.user and not request.user.is_staff and not request.user.is_superuser:
            raise PermissionDenied("You are not authorized to delete this notification.")

        notification.delete()
        return Response({"message": "✅ Notification deleted."}, status=status.HTTP_204_NO_CONTENT)
