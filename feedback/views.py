from rest_framework import viewsets, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
import logging

from notifications.models import Notification
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from .serializers import (
    GeneralFeedbackSerializer,
    ManagerFeedbackSerializer,
    ClientFeedbackSerializer,
)
from .permissions import IsAdminOrManager

logger = logging.getLogger(__name__)


# ===========================================================
# ✅ General Feedback ViewSet
# ===========================================================
class GeneralFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles General Feedback:
    - Admins and Managers can view/create/update/delete feedback.
    - Automatically triggers notifications for employees.
    """

    queryset = (
        GeneralFeedback.objects.select_related("employee__user", "department", "created_by")
        .only("employee", "department", "rating", "feedback_date", "feedback_text", "created_by")
        .all()
    )
    serializer_class = GeneralFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        """Attach creator, send notification, and return message."""
        instance = serializer.save(created_by=self.request.user)
        self._notify(instance, "📝 New general feedback added")
        logger.info(f"✅ General Feedback added for {instance.employee.user.emp_id}")
        return instance

    def _notify(self, instance, message):
        """Safe notification creation."""
        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=f"{message} on {instance.feedback_date.strftime('%d %b %Y')}.",
                auto_delete=False,
            )
        except Exception as e:
            logger.warning(f"⚠️ Notification failed (GeneralFeedback): {e}")


# ===========================================================
# ✅ Manager Feedback ViewSet
# ===========================================================
class ManagerFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Manager Feedback:
    - Managers: can create for their own team members.
    - Admins: can view all.
    - Employees: can only view their public feedback.
    """

    queryset = (
        ManagerFeedback.objects.select_related("employee__user", "department", "created_by")
        .only("employee", "department", "rating", "feedback_text", "manager_name", "created_by")
        .all()
    )
    serializer_class = ManagerFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Role-based filtering."""
        user = self.request.user
        qs = super().get_queryset()

        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return qs
        elif getattr(user, "role", "") == "Manager":
            return qs.filter(Q(created_by=user) | Q(employee__manager__user=user)).distinct()
        elif getattr(user, "role", "") == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    def perform_create(self, serializer):
        """Attach manager_name and trigger notification."""
        manager_name = f"{self.request.user.first_name} {self.request.user.last_name}".strip()
        instance = serializer.save(created_by=self.request.user, manager_name=manager_name)
        self._notify(instance, f"📋 Manager {manager_name} added feedback")
        logger.info(f"✅ Manager Feedback added by {manager_name} for {instance.employee.user.emp_id}")

    def _notify(self, instance, message):
        """Safe notification helper."""
        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=f"{message} on {instance.feedback_date.strftime('%d %b %Y')}.",
                auto_delete=False,
            )
        except Exception as e:
            logger.warning(f"⚠️ Notification failed (ManagerFeedback): {e}")


# ===========================================================
# ✅ Client Feedback ViewSet
# ===========================================================
class ClientFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Client Feedback:
    - Admins: full access
    - Managers: view public
    - Employees: view public feedback only
    - Authenticated clients: can create
    """

    queryset = (
        ClientFeedback.objects.select_related("employee__user", "department", "created_by")
        .only("employee", "department", "rating", "feedback_text", "client_name", "created_by")
        .all()
    )
    serializer_class = ClientFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["client_name", "employee__user__first_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Role-based visibility control."""
        user = self.request.user
        qs = super().get_queryset()

        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return qs
        elif getattr(user, "role", "") == "Manager":
            return qs.filter(visibility="Public")
        elif getattr(user, "role", "") == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    def perform_create(self, serializer):
        """Auto-fill client name and send notification."""
        client_name = getattr(self.request.user, "username", None) or "Client"
        instance = serializer.save(created_by=self.request.user, client_name=client_name)
        self._notify(instance, f"💬 Client feedback received from {client_name}")
        logger.info(f"✅ Client Feedback submitted by {client_name} for {instance.employee.user.emp_id}")

    def _notify(self, instance, message):
        """Notification safe wrapper."""
        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=f"{message} on {instance.feedback_date.strftime('%d %b %Y')}.",
                auto_delete=False,
            )
        except Exception as e:
            logger.warning(f"⚠️ Notification failed (ClientFeedback): {e}")


# ===========================================================
# ✅ My Feedback API (Employee Dashboard)
# ===========================================================
class MyFeedbackView(APIView):
    """
    Employee Dashboard View:
    Shows all feedback (General, Manager, Client) for the logged-in employee.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if getattr(user, "role", "") != "Employee":
            return Response(
                {"error": "Only employees can view their feedback."},
                status=status.HTTP_403_FORBIDDEN,
            )

        general_qs = GeneralFeedback.objects.filter(employee__user=user)
        manager_qs = ManagerFeedback.objects.filter(employee__user=user)
        client_qs = ClientFeedback.objects.filter(employee__user=user, visibility="Public")

        data = {
            "general_feedback": GeneralFeedbackSerializer(general_qs, many=True).data,
            "manager_feedback": ManagerFeedbackSerializer(manager_qs, many=True).data,
            "client_feedback": ClientFeedbackSerializer(client_qs, many=True).data,
        }

        summary = {
            "employee": f"{user.first_name} {user.last_name}".strip(),
            "total_general": general_qs.count(),
            "total_manager": manager_qs.count(),
            "total_client": client_qs.count(),
        }

        return Response(
            {"summary": summary, "records": data},
            status=status.HTTP_200_OK,
        )
