# ===========================================================
# feedback/views.py (Final — Frontend + Business Logic Aligned)
# ===========================================================
from rest_framework import viewsets, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
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
# 🔹 Helper — Notification Creator
# ===========================================================
def create_notification(employee_user, message):
    """Safe reusable notification helper."""
    try:
        Notification.objects.create(
            employee=employee_user,
            message=message,
            auto_delete=False,
        )
    except Exception as e:
        logger.warning(f"⚠️ Notification failed: {e}")


# ===========================================================
# ✅ General Feedback ViewSet
# ===========================================================
class GeneralFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles General Feedback.
    Admins & Managers can add/view/update/delete.
    """

    queryset = GeneralFeedback.objects.select_related("employee__user", "department", "created_by").all()
    serializer_class = GeneralFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrManager]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["employee__user__first_name", "employee__user__last_name", "feedback_text"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        instance = serializer.save(created_by=self.request.user)
        msg = f"📝 New general feedback added on {instance.feedback_date.strftime('%d %b %Y')}."
        create_notification(instance.employee.user, msg)
        logger.info(f"[GeneralFeedback] Added for {instance.employee.user.emp_id} by {self.request.user.username}")
        return instance

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {
                "message": "✅ General feedback recorded successfully.",
                "data": GeneralFeedbackSerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# ✅ Manager Feedback ViewSet
# ===========================================================
class ManagerFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Manager Feedback.
    - Managers: can create for their team members.
    - Admins: can view all.
    - Employees: view only public feedback.
    """

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

        if user.is_superuser or role == "Admin":
            return qs
        elif role == "Manager":
            return qs.filter(Q(created_by=user) | Q(employee__manager__user=user)).distinct()
        elif role == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    def perform_create(self, serializer):
        manager_name = f"{self.request.user.first_name} {self.request.user.last_name}".strip()
        instance = serializer.save(created_by=self.request.user, manager_name=manager_name)
        msg = f"📋 Manager {manager_name} submitted feedback on {instance.feedback_date.strftime('%d %b %Y')}."
        create_notification(instance.employee.user, msg)
        logger.info(f"[ManagerFeedback] Added by {manager_name} for {instance.employee.user.emp_id}")
        return instance

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {
                "message": "✅ Manager feedback submitted successfully.",
                "data": ManagerFeedbackSerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# ✅ Client Feedback ViewSet
# ===========================================================
class ClientFeedbackViewSet(viewsets.ModelViewSet):
    """
    Handles Client Feedback.
    - Admins: full access
    - Managers: view public
    - Employees: view public feedback
    """

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

        if user.is_superuser or role == "Admin":
            return qs
        elif role == "Manager":
            return qs.filter(visibility="Public")
        elif role == "Employee":
            return qs.filter(employee__user=user, visibility="Public")
        return qs.none()

    def perform_create(self, serializer):
        client_name = getattr(self.request.user, "username", None) or "Client"
        instance = serializer.save(created_by=self.request.user, client_name=client_name)
        msg = f"💬 Client feedback received from {client_name} on {instance.feedback_date.strftime('%d %b %Y')}."
        create_notification(instance.employee.user, msg)
        logger.info(f"[ClientFeedback] Submitted by {client_name} for {instance.employee.user.emp_id}")
        return instance

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        instance = self.perform_create(serializer)
        return Response(
            {
                "message": "✅ Client feedback recorded successfully.",
                "data": ClientFeedbackSerializer(instance).data,
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# ✅ My Feedback (Employee Dashboard)
# ===========================================================
class MyFeedbackView(APIView):
    """
    Displays all feedback for the logged-in employee.
    Used in Employee Dashboard (tabbed feedback view).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, "role", "")

        if role != "Employee":
            return Response(
                {"error": "Access denied. Only employees can view their feedback."},
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
            "overall_count": general_qs.count() + manager_qs.count() + client_qs.count(),
        }

        return Response(
            {
                "message": "✅ Employee feedback summary retrieved successfully.",
                "summary": summary,
                "records": data,
            },
            status=status.HTTP_200_OK,
        )
