# ===========================================================
# feedback/views.py
# ===========================================================

from rest_framework import viewsets, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q
import logging

from notifications.models import Notification
from employee.models import Employee, Department
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback
from .serializers import (
    GeneralFeedbackSerializer,
    ManagerFeedbackSerializer,
    ClientFeedbackSerializer,
)
from .permissions import IsAdminOrManager

logger = logging.getLogger(__name__)


# ===========================================================
# 🔹 Helper — Safe Notification + Role Checks
# ===========================================================
def create_notification(employee_user, message):
    """Reusable notification helper with error isolation."""
    try:
        Notification.objects.create(employee=employee_user, message=message, auto_delete=False)
        logger.info(f"Notification created for {employee_user.emp_id}")
    except Exception as e:
        logger.warning(f"Notification failed for {employee_user.emp_id if employee_user else 'N/A'}: {e}")


def is_admin(user):
    return user.is_superuser or getattr(user, "role", "") == "Admin"


def is_manager(user):
    return getattr(user, "role", "") == "Manager"


def is_admin_or_manager(user):
    return user.is_superuser or getattr(user, "role", "") in ["Admin", "Manager"]


# ===========================================================
# General Feedback ViewSet
# ===========================================================
class GeneralFeedbackViewSet(viewsets.ModelViewSet):
    """Admins & Managers can manage General Feedback."""

    queryset = GeneralFeedback.objects.select_related("employee__user", "department", "created_by").all()
    serializer_class = GeneralFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    @transaction.atomic
    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        msg = f"General feedback added on {instance.feedback_date.strftime('%d %b %Y')}."
        create_notification(instance.employee.user, msg)
        logger.info(f"[GeneralFeedback] {instance.employee.user.emp_id} by {self.request.user.username}")
        return instance

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {
                "message": "General feedback recorded successfully.",
                "data": GeneralFeedbackSerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# Manager Feedback ViewSet
# ===========================================================
class ManagerFeedbackViewSet(viewsets.ModelViewSet):
    """Managers/Admins handle feedback for team members."""

    queryset = ManagerFeedback.objects.select_related("employee__user", "department", "created_by").all()
    serializer_class = ManagerFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", "")
        qs = super().get_queryset()

        if is_admin(user):
            return qs
        elif is_manager(user):
            return qs.filter(Q(created_by=user) | Q(employee__manager__user=user)).distinct()
        elif role == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    @transaction.atomic
    def perform_create(self, serializer):
        manager_name = f"{self.request.user.first_name} {self.request.user.last_name}".strip()
        instance = serializer.save(created_by=self.request.user, manager_name=manager_name)
        msg = f"Manager {manager_name} submitted feedback on {instance.feedback_date.strftime('%d %b %Y')}."
        create_notification(instance.employee.user, msg)

        # Ensure department sync
        if instance.employee.department and instance.department != instance.employee.department:
            instance.department = instance.employee.department
            instance.save(update_fields=["department"])

        logger.info(f"[ManagerFeedback] Added by {manager_name} → {instance.employee.user.emp_id}")
        return instance

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {"message": "Manager feedback submitted successfully.",
             "data": ManagerFeedbackSerializer(instance).data},
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# Client Feedback ViewSet
# ===========================================================
class ClientFeedbackViewSet(viewsets.ModelViewSet):
    """Client feedback for employees (Admins: full, others: filtered)."""

    queryset = ClientFeedback.objects.select_related("employee__user", "department", "created_by").all()
    serializer_class = ClientFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["client_name", "employee__user__first_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, "role", "")
        qs = super().get_queryset()

        if is_admin(user):
            return qs
        elif is_manager(user):
            return qs.filter(visibility="Public")
        elif role == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    @transaction.atomic
    def perform_create(self, serializer):
        client_name = getattr(self.request.user, "username", "Client")
        instance = serializer.save(created_by=self.request.user, client_name=client_name)
        msg = f"💬 Client feedback received from {client_name} on {instance.feedback_date.strftime('%d %b %Y')}."
        create_notification(instance.employee.user, msg)

        # Ensure department auto-sync
        if instance.employee.department and instance.department != instance.employee.department:
            instance.department = instance.employee.department
            instance.save(update_fields=["department"])

        logger.info(f"[ClientFeedback] {client_name} → {instance.employee.user.emp_id}")
        return instance

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {"message": "Client feedback recorded successfully.",
             "data": ClientFeedbackSerializer(instance).data},
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# My Feedback (Employee Dashboard)
# ===========================================================
class MyFeedbackView(APIView):
    """Displays all feedback for the logged-in employee (Dashboard view)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, "role", "") != "Employee":
            return Response(
                {"error": "Access denied. Only employees can view their feedback."},
                status=status.HTTP_403_FORBIDDEN,
            )

        general_qs = GeneralFeedback.objects.filter(employee__user=user)
        manager_qs = ManagerFeedback.objects.filter(employee__user=user)
        client_qs = ClientFeedback.objects.filter(employee__user=user, visibility="Public")

        summary = {
            "employee": f"{user.first_name} {user.last_name}".strip(),
            "total_general": general_qs.count(),
            "total_manager": manager_qs.count(),
            "total_client": client_qs.count(),
            "overall_count": general_qs.count() + manager_qs.count() + client_qs.count(),
        }

        data = {
            "general_feedback": GeneralFeedbackSerializer(general_qs, many=True).data,
            "manager_feedback": ManagerFeedbackSerializer(manager_qs, many=True).data,
            "client_feedback": ClientFeedbackSerializer(client_qs, many=True).data,
        }

        logger.info(f"Feedback summary fetched for {user.emp_id}")
        return Response(
            {"message": "Feedback summary retrieved successfully.",
             "summary": summary,
             "records": data},
            status=200,
        )
