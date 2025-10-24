# ===============================================
# feedback/views.py (Final Synced Version)
# ===============================================

from rest_framework import viewsets, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from notifications.models import Notification
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from .serializers import (
    GeneralFeedbackSerializer,
    ManagerFeedbackSerializer,
    ClientFeedbackSerializer,
)
from .permissions import IsAdminOrManager


# ==============================================================
# ✅ GENERAL FEEDBACK VIEWSET
# ==============================================================
class GeneralFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles General Feedback operations:
    - Admins and Managers can view, create, and update feedback.
    - Automatically triggers notifications to employees.
    """

    queryset = GeneralFeedback.objects.select_related(
        "employee__user", "department", "created_by"
    ).all()
    serializer_class = GeneralFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        """Attach creator and trigger notification."""
        instance = serializer.save(created_by=self.request.user)

        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=f"📝 New general feedback added on {instance.feedback_date}.",
                auto_delete=False,
            )
        except Exception:
            pass


# ==============================================================
# ✅ MANAGER FEEDBACK VIEWSET
# ==============================================================
class ManagerFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Manager Feedback:
    - Managers: can create for their team members
    - Admins/Superusers: can view all
    - Employees: can view only public feedback
    """

    queryset = ManagerFeedback.objects.select_related(
        "employee__user", "department", "created_by"
    ).all()
    serializer_class = ManagerFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Restrict visibility by user role."""
        user = self.request.user
        qs = super().get_queryset()

        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return qs
        if getattr(user, "role", "") == "Manager":
            return qs.filter(Q(created_by=user) | Q(employee__manager__user=user)).distinct()
        if getattr(user, "role", "") == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    def perform_create(self, serializer):
        """Auto-assign manager_name and trigger notification."""
        manager_name = f"{self.request.user.first_name} {self.request.user.last_name}".strip()
        instance = serializer.save(created_by=self.request.user, manager_name=manager_name)

        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=f"📋 Manager {manager_name} added feedback on {instance.feedback_date}.",
                auto_delete=False,
            )
        except Exception:
            pass


# ==============================================================
# ✅ CLIENT FEEDBACK VIEWSET
# ==============================================================
class ClientFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Client Feedback:
    - Admins/Managers: can view all
    - Employees: view only public feedback related to them
    - Authenticated clients: can create
    """

    queryset = ClientFeedback.objects.select_related(
        "employee__user", "department", "created_by"
    ).all()
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
        if getattr(user, "role", "") == "Manager":
            return qs.filter(visibility="Public")
        if getattr(user, "role", "") == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    def perform_create(self, serializer):
        """Auto-fill client_name and trigger notification."""
        client_name = getattr(self.request.user, "username", None) or "Client"
        instance = serializer.save(created_by=self.request.user, client_name=client_name)

        try:
            Notification.objects.create(
                employee=instance.employee.user,
                message=f"💬 Client feedback received from {client_name} on {instance.feedback_date}.",
                auto_delete=False,
            )
        except Exception:
            pass


# ==============================================================
# ✅ MY FEEDBACK (EMPLOYEE DASHBOARD)
# ==============================================================
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

        general_feedback = GeneralFeedback.objects.filter(employee__user=user)
        manager_feedback = ManagerFeedback.objects.filter(employee__user=user)
        client_feedback = ClientFeedback.objects.filter(employee__user=user, visibility="Public")

        data = {
            "general_feedback": GeneralFeedbackSerializer(general_feedback, many=True).data,
            "manager_feedback": ManagerFeedbackSerializer(manager_feedback, many=True).data,
            "client_feedback": ClientFeedbackSerializer(client_feedback, many=True).data,
        }

        return Response(data, status=status.HTTP_200_OK)
