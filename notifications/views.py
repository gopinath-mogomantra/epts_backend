# ===============================================
# notifications/views.py (Final Updated Version)
# ===============================================

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q

from .models import Notification
from .serializers import NotificationSerializer


# ===============================================================
# ✅ Notification List View (Unified for All Roles)
# ===============================================================
class NotificationListView(generics.ListAPIView):
    """
    Fetches notifications for the logged-in user.
    Supports filters via query params:
      ?status=unread → Unread only (default)
      ?status=read   → Read only
      ?status=all    → All notifications
      ?auto_delete=true → Filter only auto-delete type
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        status_filter = self.request.query_params.get("status", "unread").lower()
        auto_delete_filter = self.request.query_params.get("auto_delete", None)

        qs = Notification.objects.filter(employee=user).select_related("employee", "department")

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
        serializer = self.get_serializer(queryset, many=True)
        total_unread = queryset.filter(is_read=False).count()
        return Response(
            {
                "count": queryset.count(),
                "unread_count": total_unread,
                "notifications": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


# ===============================================================
# ✅ Mark Notification as Read (Auto-delete if Needed)
# ===============================================================
class MarkNotificationReadView(generics.GenericAPIView):
    """
    Marks a specific notification as read.
    Automatically deletes it if `auto_delete=True`.
    """

    permission_classes = [IsAuthenticated]
    queryset = Notification.objects.all()

    def patch(self, request, pk):
        try:
            notification = self.get_queryset().get(pk=pk)
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if notification.employee != request.user:
            raise PermissionDenied("You are not authorized to modify this notification.")

        # Mark as read or delete
        notification.mark_as_read()

        msg = (
            "✅ Notification marked as read and deleted automatically."
            if notification.auto_delete
            else "✅ Notification marked as read."
        )

        return Response(
            {"message": msg, "notification_id": pk},
            status=status.HTTP_200_OK,
        )


# ===============================================================
# ✅ Bulk Mark All Notifications as Read
# ===============================================================
class MarkAllNotificationsReadView(generics.GenericAPIView):
    """
    Marks all unread notifications for the logged-in user as read.
    Auto-deletes temporary ones.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        notifications = Notification.objects.filter(employee=user, is_read=False)

        count = notifications.count()
        for note in notifications:
            note.mark_as_read()

        return Response(
            {"message": f"✅ {count} notifications marked as read."},
            status=status.HTTP_200_OK,
        )
