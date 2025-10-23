# ===============================================
# notifications/views.py
# ===============================================

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from .models import Notification
from .serializers import NotificationSerializer


# ===============================================================
# Notification List View (Single Unified Endpoint)
# ===============================================================
class NotificationListView(generics.ListAPIView):
    """
    Returns notifications for the logged-in employee.
    Query Params:
        ?status=unread → Unread notifications only (default)
        ?status=read   → Only read notifications
        ?status=all    → All notifications
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        status_filter = self.request.query_params.get("status", "unread")

        qs = Notification.objects.filter(employee=user).order_by("-created_at")

        if status_filter == "unread":
            qs = qs.filter(is_read=False)
        elif status_filter == "read":
            qs = qs.filter(is_read=True)
        elif status_filter == "all":
            pass
        else:
            qs = qs.filter(is_read=False)

        return qs


# ===============================================================
# Mark Notification as Read (Auto-delete if Needed)
# ===============================================================
class MarkNotificationReadView(generics.GenericAPIView):
    """
    Marks a notification as read.
    If auto_delete=True → deletes it after marking.
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

        notification.mark_as_read()

        msg = (
            "Notification marked as read and deleted."
            if notification.auto_delete
            else "Notification marked as read."
        )

        return Response({"message": msg}, status=status.HTTP_200_OK)
