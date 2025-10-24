# ===============================================
# employee/views.py  (Frontend-Aligned & Demo Ready — 2025-10-24)
# ===============================================

from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db import models
from rest_framework.pagination import PageNumberPagination

from .models import Department, Employee
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer,
    EmployeeCreateUpdateSerializer,
)

User = get_user_model()


# ============================================================
# ✅ PAGINATION CLASS (for Team Members)
# ============================================================
class TeamPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 50


# ============================================================
# ✅ DEPARTMENT VIEWSET
# ============================================================
class DepartmentViewSet(viewsets.ModelViewSet):
    """CRUD for Departments using department.code as the lookup key."""
    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    lookup_field = "code"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description", "code"]
    ordering_fields = ["name", "created_at", "code"]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        include_inactive = self.request.query_params.get("include_inactive")
        user = self.request.user
        if include_inactive and include_inactive.lower() == "true":
            if user.is_superuser or getattr(user, "role", "") == "Admin":
                return qs
        return qs.filter(is_active=True)

    def get_object(self):
        code = self.kwargs.get(self.lookup_field)
        include_inactive = self.request.query_params.get("include_inactive")
        user = self.request.user
        try:
            dept = Department.objects.get(code__iexact=code)
        except Department.DoesNotExist:
            raise NotFound(detail=f"Department with code '{code}' not found.")
        if not dept.is_active:
            if not (include_inactive and (user.is_superuser or getattr(user, "role", "") == "Admin")):
                raise NotFound(detail=f"Department with code '{code}' not found or inactive.")
        return dept

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can create departments."}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can update departments."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") == "Admin"):
            return Response({"error": "Only Admins can delete departments."}, status=status.HTTP_403_FORBIDDEN)

        force_delete = request.query_params.get("force", "").lower() == "true"
        if force_delete:
            instance.delete()
            return Response(
                {"message": f"🗑️ Department '{instance.name}' permanently deleted."},
                status=status.HTTP_204_NO_CONTENT,
            )

        if instance.employees.exists():
            return Response(
                {"error": "Cannot delete a department with assigned employees."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        instance.is_active = False
        instance.save(update_fields=["is_active"])
        return Response({"message": "🗑️ Department deactivated successfully."}, status=status.HTTP_200_OK)


# ============================================================
# ✅ EMPLOYEE VIEWSET
# ============================================================
class EmployeeViewSet(viewsets.ModelViewSet):
    """Unified CRUD ViewSet for Employees (lookup by user.emp_id)."""

    queryset = Employee.objects.select_related("user", "department", "manager").prefetch_related("team_members")
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["department", "manager", "status", "is_active"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__emp_id",
        "designation",
        "contact_number",
        "department__name",
    ]
    ordering_fields = ["joining_date", "user__first_name", "user__emp_id"]
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "emp_id"

    # --------------------------------------------------------
    # Role-Based Query Restriction
    # --------------------------------------------------------
    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if getattr(user, "role", "") == "Manager":
            return qs.filter(manager__user=user)
        elif getattr(user, "role", "") == "Employee":
            return qs.filter(user=user)
        return qs

    # --------------------------------------------------------
    # Fetch Object via emp_id
    # --------------------------------------------------------
    def get_object(self):
        emp_id = self.kwargs.get("emp_id")
        try:
            return Employee.objects.select_related("user", "department", "manager").get(
                user__emp_id__iexact=emp_id
            )
        except Employee.DoesNotExist:
            raise NotFound(detail=f"Employee with emp_id '{emp_id}' not found.")

    # --------------------------------------------------------
    # Serializer Switch
    # --------------------------------------------------------
    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return EmployeeCreateUpdateSerializer
        return EmployeeSerializer

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------
    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", "") in ["Admin", "Manager"]):
            return Response(
                {"error": "You do not have permission to create employees."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.save()

        return Response(
            {"message": "✅ Employee created successfully.",
             "employee": EmployeeSerializer(employee, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )

    # --------------------------------------------------------
    # RETRIEVE
    # --------------------------------------------------------
    def retrieve(self, request, *args, **kwargs):
        employee = self.get_object()
        user = request.user
        if getattr(user, "role", "") == "Manager" and (not employee.manager or employee.manager.user != user):
            return Response({"error": "Managers can view only their team members."}, status=status.HTTP_403_FORBIDDEN)
        if getattr(user, "role", "") == "Employee" and employee.user != user:
            return Response({"error": "Employees can view only their own record."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(employee)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------
    def update(self, request, *args, **kwargs):
        employee = self.get_object()
        user = request.user
        if getattr(user, "role", "") == "Manager" and (not employee.manager or employee.manager.user != user):
            return Response({"error": "Managers can update only their team members."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(employee, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "✅ Employee updated successfully.",
             "employee": EmployeeSerializer(employee, context={"request": request}).data},
            status=status.HTTP_200_OK,
        )

    # --------------------------------------------------------
    # DELETE
    # --------------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        employee = self.get_object()
        user = request.user
        if getattr(employee.user, "role", "") in ["Admin", "Manager"]:
            return Response({"error": "❌ Cannot delete Admin or Manager accounts."}, status=status.HTTP_403_FORBIDDEN)
        if not (user.is_superuser or getattr(user, "role", "") in ["Admin", "Manager"]):
            return Response({"error": "You do not have permission to delete employees."}, status=status.HTTP_403_FORBIDDEN)
        employee.user.delete()
        employee.delete()
        return Response({"message": "🗑️ Employee deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    # --------------------------------------------------------
    # TEAM LIST (Filtering, Search & Pagination)
    # --------------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"team/(?P<manager_emp_id>[^/.]+)")
    def get_team(self, request, manager_emp_id=None):
        """Paginated & Filtered Team List."""
        try:
            manager = Employee.objects.select_related("user", "department").get(user__emp_id__iexact=manager_emp_id)
        except Employee.DoesNotExist:
            return Response({"error": f"Manager with emp_id '{manager_emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)
        if manager.user.role != "Manager":
            return Response({"error": f"User '{manager_emp_id}' is not a Manager."}, status=status.HTTP_400_BAD_REQUEST)

        team_members = Employee.objects.select_related("user", "department").filter(manager=manager)
        status_filter = request.query_params.get("status")
        dept_code = request.query_params.get("department_code")
        search_query = request.query_params.get("search")

        if status_filter:
            team_members = team_members.filter(status__iexact=status_filter)
        if dept_code:
            team_members = team_members.filter(department__code__iexact=dept_code)
        if search_query:
            team_members = team_members.filter(
                models.Q(user__first_name__icontains=search_query)
                | models.Q(user__last_name__icontains=search_query)
                | models.Q(designation__icontains=search_query)
            )

        paginator = TeamPagination()
        paginated_qs = paginator.paginate_queryset(team_members, request)

        team_data = [{
            "emp_id": e.user.emp_id,
            "name": f"{e.user.first_name} {e.user.last_name}".strip(),
            "designation": e.designation,
            "department": e.department.name if e.department else None,
            "status": e.status,
        } for e in paginated_qs]

        response_data = {
            "manager": {
                "emp_id": manager.user.emp_id,
                "name": f"{manager.user.first_name} {manager.user.last_name}".strip(),
                "department": manager.department.name if manager.department else None,
                "designation": manager.designation,
                "status": manager.status,
            },
            "filters": {"status": status_filter or "All", "department_code": dept_code or "All", "search": search_query or ""},
            "total_team_members": team_members.count(),
            "page": paginator.page.number if getattr(paginator, "page", None) else 1,
            "page_size": paginator.get_page_size(request),
            "total_pages": paginator.page.paginator.num_pages if getattr(paginator, "page", None) else 1,
            "team_members": team_data,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    # --------------------------------------------------------
    # TEAM OVERVIEW (Safe Version — Step 4.9)
    # --------------------------------------------------------
    @action(detail=False, methods=["get"], url_path=r"team/(?P<manager_emp_id>[^/.]+)/overview")
    def get_team_overview(self, request, manager_emp_id=None):
        """Return summarized team performance metrics for manager dashboards."""
        try:
            manager = Employee.objects.select_related("user", "department").get(user__emp_id__iexact=manager_emp_id)
        except Employee.DoesNotExist:
            return Response({"error": f"Manager with emp_id '{manager_emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        if manager.user.role != "Manager":
            return Response({"error": f"User '{manager_emp_id}' is not a Manager."}, status=status.HTTP_400_BAD_REQUEST)

        team_members = Employee.objects.filter(manager=manager, is_active=True)
        if not team_members.exists():
            return Response(
                {"message": f"No team members found under {manager.user.first_name} {manager.user.last_name}."},
                status=status.HTTP_200_OK,
            )

        # --- Defensive Import ---
        try:
            from attendance.models import Attendance
        except ImportError:
            Attendance = None
        try:
            from feedback.models import Feedback
        except Exception:
            Feedback = None
        try:
            from performance.models import TaskPerformance
        except Exception:
            TaskPerformance = None

        # --- Compute Safe Averages ---
        avg_attendance = 0
        avg_feedback = 0
        avg_completion = 0
        top_performers = []
        weak_performers = []

        if Attendance:
            avg_attendance = Attendance.objects.filter(
                emp_id__in=team_members.values_list("id", flat=True)
            ).aggregate(models.Avg("worked_hours")).get("worked_hours__avg") or 0

        if Feedback:
            avg_feedback = Feedback.objects.filter(
                emp_id__in=team_members.values_list("id", flat=True)
            ).aggregate(models.Avg("rating")).get("rating__avg") or 0

        if TaskPerformance:
            avg_completion = TaskPerformance.objects.filter(
                emp_id__in=team_members.values_list("id", flat=True)
            ).aggregate(models.Avg("completion_rate")).get("completion_rate__avg") or 0

            top_performers = TaskPerformance.objects.filter(
                emp_id__in=team_members.values_list("id", flat=True)
            ).order_by("-overall_score")[:3].values(
                "emp__user__emp_id", "emp__user__first_name", "emp__user__last_name", "overall_score"
            )
            weak_performers = TaskPerformance.objects.filter(
                emp_id__in=team_members.values_list("id", flat=True)
            ).order_by("overall_score")[:3].values(
                "emp__user__emp_id", "emp__user__first_name", "emp__user__last_name", "overall_score"
            )

        response_data = {
            "manager": {
                "emp_id": manager.user.emp_id,
                "name": f"{manager.user.first_name} {manager.user.last_name}".strip(),
                "department": manager.department.name if manager.department else None,
                "designation": manager.designation,
            },
            "summary": {
                "total_team_members": team_members.count(),
                "active_members": team_members.filter(status="Active").count(),
                "inactive_members": team_members.filter(status="Inactive").count(),
                "average_attendance_hours": round(avg_attendance, 2),
                "average_task_completion_rate": round(avg_completion, 2),
                "average_feedback_score": round(avg_feedback, 2),
            },
            "top_performers": [
                {"emp_id": tp["emp__user__emp_id"],
                 "name": f"{tp['emp__user__first_name']} {tp['emp__user__last_name']}".strip(),
                 "score": round(tp["overall_score"], 2)} for tp in top_performers
            ],
            "weak_performers": [
                {"emp_id": wp["emp__user__emp_id"],
                 "name": f"{wp['emp__user__first_name']} {wp['emp__user__last_name']}".strip(),
                 "score": round(wp["overall_score"], 2)} for wp in weak_performers
            ],
        }
        return Response(response_data, status=status.HTTP_200_OK)
