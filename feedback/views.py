# feedback/views.py
from rest_framework import viewsets, permissions, filters
from django.db import models
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from .serializers import (
    GeneralFeedbackSerializer,
    ManagerFeedbackSerializer,
    ClientFeedbackSerializer,
)
from .permissions import IsAdminOrManager, IsCreatorOrAdmin


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
    search_fields = [
        "employee__user__first_name",
        "employee__user__last_name",
        "feedback_text",
    ]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        """Automatically set the creator of the feedback."""
        serializer.save(created_by=self.request.user)


class ManagerFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Manager Feedback:
    - Managers can create feedback for their teams/subordinates.
    - Admins and Superusers can view all.
    """

    queryset = ManagerFeedback.objects.select_related(
        "employee__user", "department", "created_by"
    )
    serializer_class = ManagerFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "employee__user__first_name",
        "employee__user__last_name",
        "feedback_text",
    ]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Restrict feedback visibility based on user role."""
        user = self.request.user
        qs = super().get_queryset()

        # Admins and Superusers: view all
        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return qs

        # Managers: view their own feedback + feedback for subordinates
        if getattr(user, "role", "") == "Manager":
            return qs.filter(
                models.Q(created_by=user) | models.Q(employee__manager__user=user)
            ).distinct()

        # Employees: see only their own feedback that is public
        if getattr(user, "role", "") == "Employee":
            return qs.filter(employee__user=user, visibility="Public")

        return qs.none()

    def perform_create(self, serializer):
        """Assign manager_name and created_by automatically."""
        manager_name = f"{self.request.user.first_name} {self.request.user.last_name}".strip()
        serializer.save(created_by=self.request.user, manager_name=manager_name)


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
    search_fields = [
        "client_name",
        "employee__user__first_name",
        "feedback_text",
    ]
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
        """Automatically set created_by and default client_name."""
        client_name = getattr(self.request.user, "username", None) or "Client"
        serializer.save(created_by=self.request.user, client_name=client_name)
