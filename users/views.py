# ===========================================================
# users/views.py ✅ Frontend-Aligned & Serializer-Compatible
# Employee Performance Tracking System (EPTS)
# ===========================================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction, models
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
import logging

from employee.models import Employee, Department
from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    ProfileSerializer,
    ChangePasswordSerializer,
)

logger = logging.getLogger("users")
User = get_user_model()


# ===========================================================
# ✅ 1. LOGIN (Supports username / emp_id / email)
# ===========================================================
class ObtainTokenPairView(TokenObtainPairView):
    """
    POST /api/users/login/
    Handles login via emp_id, username, or email.
    Returns JWT tokens + user payload.
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.warning(f"Login failed: {e}")
            return Response(
                {"detail": str(e), "status": "failed"},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        return Response(
            {
                "refresh": data.get("refresh"),
                "access": data.get("access"),
                "user": data.get("user"),
                "status": "success",
                "message": "Login successful."
            },
            status=status.HTTP_200_OK
        )


# ===========================================================
# ✅ 2. REFRESH TOKEN
# ===========================================================
class RefreshTokenView(TokenRefreshView):
    """
    POST /api/users/token/refresh/
    Returns new access token using refresh token.
    """
    permission_classes = [AllowAny]


# ===========================================================
# ✅ 3. REGISTER USER (Admin / Manager)
# ===========================================================
class RegisterView(generics.CreateAPIView):
    """
    POST /api/users/register/
    Allows Admin or Manager to register new users.
    Also creates a corresponding Employee record.
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        current_user = request.user

        # Role-based access control
        if not (current_user.is_admin() or current_user.is_manager()):
            return Response(
                {"error": "Access denied. Only Admin or Manager can create users."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data.get("email")
        if User.objects.filter(email__iexact=email).exists():
            return Response({"error": "User with this email already exists."}, status=400)

        # Create user
        user = serializer.save()
        if not user.joining_date:
            user.joining_date = timezone.now().date()
            user.save(update_fields=["joining_date"])

        # Auto-create Employee record
        dept_value = request.data.get("department")
        department = None
        if dept_value:
            department = Department.objects.filter(
                models.Q(id__iexact=dept_value)
                | models.Q(code__iexact=dept_value)
                | models.Q(name__iexact=dept_value)
            ).first()

        if not Employee.objects.filter(user=user).exists():
            Employee.objects.create(
                user=user,
                emp_id=user.emp_id,
                department=department,
                joining_date=user.joining_date,
                status=user.status
            )

        # Send email notification (optional)
        try:
            send_mail(
                subject="EPTS - Account Created",
                message=(
                    f"Hello {user.get_full_name()},\n\n"
                    f"Your EPTS account has been created successfully.\n"
                    f"Employee ID: {user.emp_id}\n"
                    f"Temporary Password: {getattr(user, 'temp_password', 'N/A')}\n\n"
                    f"Please log in and change your password immediately.\n\n"
                    f"Regards,\nEPTS Admin Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )
        except Exception as e:
            logger.warning(f"Email send failed for {user.emp_id}: {e}")

        logger.info(f"User {user.emp_id} registered by {current_user.emp_id}")
        return Response(
            {
                "message": "✅ User registered successfully.",
                "user": ProfileSerializer(user).data,
                "temp_password": getattr(user, "temp_password", None) if settings.DEBUG else None,
            },
            status=status.HTTP_201_CREATED
        )


# ===========================================================
# ✅ 4. CHANGE PASSWORD
# ===========================================================
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        logger.info(f"Password changed for {request.user.emp_id}")
        return Response(result, status=200)


# ===========================================================
# ✅ 5. PROFILE (GET / PATCH)
# ===========================================================
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return logged-in user's profile."""
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data, status=200)

    def patch(self, request):
        """Allow user to update limited profile fields."""
        user = request.user
        editable_fields = {"first_name", "last_name", "email", "phone"}
        updates = {}

        for field, value in request.data.items():
            if field in editable_fields:
                if field == "email" and User.objects.exclude(id=user.id).filter(email__iexact=value).exists():
                    return Response({"error": "Email already exists."}, status=400)
                if field == "phone" and value and User.objects.exclude(id=user.id).filter(phone=value).exists():
                    return Response({"error": "Phone already exists."}, status=400)
                updates[field] = value

        for k, v in updates.items():
            setattr(user, k, v)

        if updates:
            user.save(update_fields=list(updates.keys()))
            logger.info(f"Profile updated by {user.emp_id}")

        return Response(
            {"message": "✅ Profile updated successfully.", "user": ProfileSerializer(user).data},
            status=200,
        )


# ===========================================================
# ✅ 6. ROLE LIST
# ===========================================================
class RoleListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Return list of available user roles."""
        roles = [role for role, _ in User.ROLE_CHOICES]
        return Response({"roles": roles}, status=200)


# ===========================================================
# ✅ 7. USER LIST (Admin Only)
# ===========================================================
class UserPagination(PageNumberPagination):
    page_size = 20


class UserListView(generics.ListAPIView):
    queryset = User.objects.select_related("department", "manager").all().order_by("emp_id")
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "emp_id", "email", "first_name", "last_name", "status"]
    ordering_fields = ["emp_id", "username", "joining_date"]
    pagination_class = UserPagination

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        dept_param = self.request.query_params.get("department")
        emp_id_param = self.request.query_params.get("emp_id")

        if status_param:
            qs = qs.filter(is_active=(status_param.lower() == "active"))
        if dept_param:
            qs = qs.filter(department__name__icontains=dept_param)
        if emp_id_param:
            qs = qs.filter(emp_id__iexact=emp_id_param)
        return qs

    def list(self, request, *args, **kwargs):
        if not request.user.is_admin():
            return Response({"error": "Access denied. Admins only."}, status=403)
        return super().list(request, *args, **kwargs)


# ===========================================================
# ✅ 8. ADMIN RESET PASSWORD
# ===========================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
@transaction.atomic
def reset_password(request):
    emp_id = request.data.get("emp_id")
    if not emp_id:
        return Response({"error": "emp_id is required."}, status=400)

    try:
        user = User.objects.get(emp_id=emp_id)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=404)

    new_password = get_random_string(
        length=10,
        allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*",
    )

    user.set_password(new_password)
    user.force_password_change = True
    user.save(update_fields=["password", "force_password_change"])

    # Email notification
    try:
        send_mail(
            subject="EPTS Password Reset Notification",
            message=(
                f"Hello {user.get_full_name()},\n\n"
                f"Your password has been reset by Admin ({request.user.emp_id}).\n"
                f"Temporary Password: {new_password}\n\n"
                f"Please log in and change your password immediately.\n\n"
                f"Regards,\nEPTS Admin Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger.warning(f"Email send failed for {user.emp_id}: {e}")

    logger.info(f"Password reset by Admin {request.user.emp_id} for user {user.emp_id}")
    response_data = {
        "message": f"✅ Password reset successfully for {user.emp_id}.",
        "username": user.username,
        "force_password_change": True,
    }
    if settings.DEBUG:
        response_data["temp_password"] = new_password
    return Response(response_data, status=200)


# ===========================================================
# ✅ 9. USER DETAIL (Admin CRUD)
# ===========================================================
class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, emp_id):
        return User.objects.filter(emp_id=emp_id).first()

    def get(self, request, emp_id):
        """Fetch single user details by emp_id."""
        user = self.get_object(emp_id)
        if not user:
            return Response({"error": "User not found."}, status=404)
        return Response(ProfileSerializer(user).data, status=200)

    @transaction.atomic
    def patch(self, request, emp_id):
        """Update user details (Admin only)."""
        admin = request.user
        if not admin.is_admin():
            return Response({"error": "Access denied. Admins only."}, status=403)

        user = self.get_object(emp_id)
        if not user:
            return Response({"error": "User not found."}, status=404)

        editable_fields = ["first_name", "last_name", "email", "phone", "is_verified", "is_active", "department", "manager"]
        updates = {f: v for f, v in request.data.items() if f in editable_fields}

        # Resolve manager
        if "manager" in updates:
            mgr_val = updates.pop("manager")
            manager_obj = (
                User.objects.filter(emp_id__iexact=mgr_val).first()
                or User.objects.filter(username__iexact=mgr_val).first()
            )
            if not manager_obj:
                return Response({"error": f"Manager '{mgr_val}' not found."}, status=400)
            updates["manager"] = manager_obj

        for k, v in updates.items():
            setattr(user, k, v)

        if updates:
            user.save(update_fields=list(updates.keys()))
            logger.info(f"User {emp_id} updated by Admin {admin.emp_id}")

        return Response(
            {"message": "✅ User updated successfully.", "user": ProfileSerializer(user).data},
            status=200,
        )

    @transaction.atomic
    def delete(self, request, emp_id):
        """Deactivate a user (soft delete)."""
        admin = request.user
        if not admin.is_admin():
            return Response({"error": "Access denied. Admins only."}, status=403)

        user = self.get_object(emp_id)
        if not user:
            return Response({"error": "User not found."}, status=404)
        if user == admin:
            return Response({"error": "You cannot deactivate your own account."}, status=400)
        if user.role == "Admin":
            return Response({"error": "Cannot deactivate another Admin account."}, status=400)

        user.is_active = False
        user.save(update_fields=["is_active"])
        logger.warning(f"User {emp_id} deactivated by Admin {admin.emp_id}")

        return Response(
            {"message": f"✅ User '{emp_id}' deactivated successfully.", "status": "Inactive"},
            status=200,
        )
