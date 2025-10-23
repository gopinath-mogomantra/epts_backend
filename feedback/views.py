# ===============================================
# feedback/views.py 
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
from .permissions import IsAdminOrManager, IsCreatorOrAdmin


# ==============================================================
# GENERAL FEEDBACK
# ==============================================================
class GeneralFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles General Feedback operations:
    - Admins and Managers can view, create, and update feedback.
    - Linked to employee and department details.
    """

    queryset = GeneralFeedback.objects.select_related(
        "employee__user", "department", "created_by"
    )
    serializer_class = GeneralFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        """Automatically set the creator of the feedback and trigger notification."""
        instance = serializer.save(created_by=self.request.user)

        # 🔔 Notification Trigger
        Notification.objects.create(
            employee=instance.employee.user,
            message=f"New general feedback has been added for you on {instance.feedback_date}.",
            auto_delete=False
        )


# ==============================================================
# MANAGER FEEDBACK
# ==============================================================
class ManagerFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Manager Feedback:
    - Managers can create feedback for their team/subordinates.
    - Admins and Superusers can view all.
    """

    queryset = ManagerFeedback.objects.select_related(
        "employee__user", "department", "created_by"
    )
    serializer_class = ManagerFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Restrict feedback visibility based on user role."""
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
        """Assign manager_name, created_by, and send notification."""
        manager_name = f"{self.request.user.first_name} {self.request.user.last_name}".strip()
        instance = serializer.save(created_by=self.request.user, manager_name=manager_name)

        # Notification Trigger
        Notification.objects.create(
            employee=instance.employee.user,
            message=f"Your manager {manager_name} added new feedback on {instance.feedback_date}.",
            auto_delete=False
        )


# ==============================================================
# CLIENT FEEDBACK
# ==============================================================
class ClientFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Client Feedback:
    - Admins and Managers can view all.
    - Authenticated users can submit feedback.
    - Employees can view only public client feedback.
    """

    queryset = ClientFeedback.objects.select_related(
        "employee__user", "department", "created_by"
    )
    serializer_class = ClientFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["client_name", "employee__user__first_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter visibility and access by user role."""
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
        """Automatically set created_by, client_name, and send notification."""
        client_name = getattr(self.request.user, "username", None) or "Client"
        instance = serializer.save(created_by=self.request.user, client_name=client_name)

        # Notification Trigger
        Notification.objects.create(
            employee=instance.employee.user,
            message=f"New client feedback received from {client_name} on {instance.feedback_date}.",
            auto_delete=False
        )


# ==============================================================
# MY FEEDBACK (Employee Dashboard View)
# ==============================================================
class MyFeedbackView(APIView):
    """
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
        client_feedback = ClientFeedback.objects.filter(employee__user=user)

        data = {
            "general_feedback": GeneralFeedbackSerializer(general_feedback, many=True).data,
            "manager_feedback": ManagerFeedbackSerializer(manager_feedback, many=True).data,
            "client_feedback": ClientFeedbackSerializer(client_feedback, many=True).data,
        }

        return Response(data, status=status.HTTP_200_OK)
