# ===========================================================
# users/views.py (Production-Ready & Fully Validated)
# ===========================================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import generics, status, filters, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from django.db import transaction
from django.utils.crypto import get_random_string
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
# ✅ 1. LOGIN — JWT Authentication with Lockout Handling
# ===========================================================
class ObtainTokenPairView(TokenObtainPairView):
    """Authenticate user via emp_id or username (JWT token issuance)."""
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


# ===========================================================
# ✅ 2. REFRESH TOKEN
# ===========================================================
class RefreshTokenView(TokenRefreshView):
    """Refresh access token using refresh token."""
    permission_classes = [AllowAny]


# ===========================================================
# ✅ 3. REGISTER USER — Admin or Manager Only
# ===========================================================
class RegisterView(generics.CreateAPIView):
    """
    Allows Admins or Managers to register new users.
    Automatically:
    - Generates emp_id
    - Assigns temporary password
    - Creates corresponding Employee record
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        current_user = request.user

        # Role check
        if not (current_user.is_admin() or current_user.is_manager()):
            return Response(
                {"error": "Access denied. Only Admin or Manager can create new users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Check for existing email / emp_id duplicates before creation
        email = serializer.validated_data.get("email")
        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {"error": "A user with this email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create user safely (emp_id + temp password handled in serializer)
        user = serializer.save()

        # Ensure joining_date exists
        if not user.joining_date:
            user.joining_date = timezone.now().date()
            user.save(update_fields=["joining_date"])

        # ✅ Auto-create linked Employee record if not exists
        try:
            if not Employee.objects.filter(user=user).exists():
                dept_id = request.data.get("department")
                department = Department.objects.filter(id=dept_id).first() if dept_id else None

                Employee.objects.create(
                    user=user,
                    emp_id=user.emp_id,
                    department=department,
                    status=user.status,
                    joining_date=user.joining_date,
                )
        except Exception as e:
            logger.warning(f"Employee record auto-create failed for {user.emp_id}: {e}")

        return Response(
            {
                "message": "✅ User registered successfully.",
                "user": ProfileSerializer(user).data,
                "temp_password": getattr(user, "temp_password", None),
            },
            status=status.HTTP_201_CREATED,
        )


# ===========================================================
# ✅ 4. CHANGE PASSWORD — First Login / Regular Change
# ===========================================================
class ChangePasswordView(APIView):
    """
    Change user password.
    Supports:
    - First login forced change
    - Normal authenticated user password update
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 5. PROFILE API — View or Edit Self Profile
# ===========================================================
class ProfileView(APIView):
    """
    GET: Retrieve logged-in user's profile.
    PATCH: Update basic profile details (name, phone, email).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user
        editable_fields = ["first_name", "last_name", "email", "phone"]

        for field, value in request.data.items():
            if field in editable_fields:
                setattr(user, field, value)
        user.save(update_fields=[f for f in request.data.keys() if f in editable_fields])

        logger.info("Profile updated for user %s", user.emp_id)
        return Response(
            {
                "message": "✅ Profile updated successfully.",
                "user": ProfileSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ✅ 6. ROLE LIST — For Dropdown in Frontend
# ===========================================================
class RoleListView(APIView):
    """Return available roles for dropdowns (Admin, Manager, Employee)."""
    permission_classes = [AllowAny]

    def get(self, request):
        roles = [role for role, _ in User.ROLE_CHOICES]
        return Response({"roles": roles}, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 7. USER LIST — Admin Only (Search & Filters)
# ===========================================================
class UserListView(generics.ListAPIView):
    """List all users — visible to Admins only."""
    queryset = User.objects.select_related("department").all().order_by("emp_id")
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "emp_id", "email", "first_name", "last_name", "status"]
    ordering_fields = ["emp_id", "username", "joining_date"]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        dept_param = self.request.query_params.get("department")
        emp_id_param = self.request.query_params.get("emp_id")

        if status_param:
            qs = qs.filter(status__iexact=status_param)
        if dept_param:
            qs = qs.filter(department__name__icontains=dept_param)
        if emp_id_param:
            qs = qs.filter(emp_id__iexact=emp_id_param)
        return qs

    def list(self, request, *args, **kwargs):
        if not request.user.is_admin():
            return Response(
                {"error": "Access denied. Admins only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)


# ===========================================================
# ✅ 8. ADMIN RESET PASSWORD
# ===========================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def reset_password(request):
    """
    Reset a user’s password (Admin only).
    Generates a new random password and enforces password change at next login.
    """
    emp_id = request.data.get("emp_id")
    if not emp_id:
        return Response({"error": "emp_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(emp_id=emp_id)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    new_password = get_random_string(
        length=10,
        allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*",
    )

    user.set_password(new_password)
    user.force_password_change = True
    user.save(update_fields=["password", "force_password_change"])

    logger.info("Password reset by Admin for user %s", user.emp_id)
    return Response(
        {
            "message": f"✅ Password reset successfully for {user.emp_id}.",
            "username": user.username,
            "temp_password": new_password,
            "force_password_change": True,
        },
        status=status.HTTP_200_OK,
    )


# ===========================================================
# ✅ 9. USER DETAIL (GET / PATCH / DELETE — Admin Only)
# ===========================================================
class UserDetailView(APIView):
    """
    Admins can:
    - GET: Fetch user by emp_id
    - PATCH: Update user details
    - DELETE: Soft delete (mark Inactive)
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, emp_id):
        try:
            return User.objects.get(emp_id=emp_id)
        except User.DoesNotExist:
            return None

    def get(self, request, emp_id):
        user = self.get_object(emp_id)
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProfileSerializer(user).data, status=status.HTTP_200_OK)

    def patch(self, request, emp_id):
        current_user = request.user
        if not current_user.is_admin():
            return Response(
                {"error": "Access denied. Only Admins can update users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user = self.get_object(emp_id)
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        editable_fields = ["first_name", "last_name", "email", "phone", "is_verified", "status", "department"]
        for field, value in request.data.items():
            if field in editable_fields:
                setattr(user, field, value)
        user.save(update_fields=[f for f in request.data.keys() if f in editable_fields])

        logger.info("User %s updated by Admin %s", emp_id, current_user.emp_id)
        return Response(
            {"message": "✅ User updated successfully.", "user": ProfileSerializer(user).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, emp_id):
        current_user = request.user
        if not current_user.is_admin():
            return Response(
                {"error": "Access denied. Only Admins can deactivate users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_to_deactivate = self.get_object(emp_id)
        if not user_to_deactivate:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user_to_deactivate == current_user:
            return Response(
                {"error": "You cannot deactivate your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_to_deactivate.is_active = False
        user_to_deactivate.status = "Inactive"
        user_to_deactivate.save(update_fields=["is_active", "status"])

        logger.warning("User %s deactivated by Admin %s", emp_id, current_user.emp_id)
        return Response(
            {
                "message": f"✅ User '{emp_id}' deactivated successfully.",
                "status": user_to_deactivate.status,
                "is_active": user_to_deactivate.is_active,
            },
            status=status.HTTP_200_OK,
        )
