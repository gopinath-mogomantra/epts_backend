# ===============================================
# users/views.py  (Frontend-Aligned & Demo Ready — 2025-10-24)
# ===============================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import get_user_model, authenticate
from django.utils import timezone
from django.utils.crypto import get_random_string

from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    ProfileSerializer,
)

User = get_user_model()


# =====================================================
# ✅ 1. LOGIN API (JWT Token Obtain View)
# =====================================================
class ObtainTokenPairView(TokenObtainPairView):
    """Authenticate user and issue JWT tokens."""
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


# =====================================================
# ✅ 2. REFRESH TOKEN API
# =====================================================
class RefreshTokenView(TokenRefreshView):
    """Refresh JWT token using valid refresh token."""
    permission_classes = [AllowAny]


# =====================================================
# ✅ 3. USER REGISTRATION (Admin / Superuser Only)
# =====================================================
class RegisterView(generics.CreateAPIView):
    """
    Allows Admins or Superusers to register a new user.
    - emp_id is auto-generated
    - joining_date auto-filled if missing
    """
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        current_user = request.user
        if not (current_user.is_superuser or getattr(current_user, "role", None) == "Admin"):
            return Response(
                {"error": "Only Admins or Superusers can create new users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_user = serializer.save()

        # Auto-fill joining date if not provided
        if not getattr(new_user, "joining_date", None):
            new_user.joining_date = timezone.now().date()
            new_user.save(update_fields=["joining_date"])

        return Response(
            {
                "message": "✅ User registered successfully.",
                "user": ProfileSerializer(new_user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =====================================================
# ✅ 4. CHANGE / FIRST-TIME PASSWORD (Combined)
# =====================================================
class ChangePasswordView(APIView):
    """
    Handles both:
    1️⃣ First-time password change (temp password)
    2️⃣ Authenticated password change (with JWT)
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        # Validate new passwords
        if not new_password or not confirm_password:
            return Response(
                {"detail": "New password and confirm password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response({"detail": "New passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        user = None

        # Case 1️⃣: First-time login (username + old password)
        if username and old_password:
            user = authenticate(username=username, password=old_password)
            if not user:
                return Response({"detail": "Invalid username or old password."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Case 2️⃣: Authenticated user via JWT
            if request.user and request.user.is_authenticated:
                user = request.user
                if not old_password:
                    return Response(
                        {"detail": "Old password is required for authenticated password change."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not user.check_password(old_password):
                    return Response({"detail": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response(
                    {"detail": "Authentication credentials were not provided."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        # Update password and clear flag
        user.set_password(new_password)
        user.force_password_change = False
        user.save(update_fields=["password", "force_password_change"])

        return Response({"message": "✅ Password changed successfully!"}, status=status.HTTP_200_OK)


# =====================================================
# ✅ 5. PROFILE API (Self)
# =====================================================
class ProfileView(APIView):
    """Return current user's profile info."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================
# ✅ 6. ROLE LIST
# =====================================================
class RoleListView(APIView):
    """Return available user roles."""
    permission_classes = [AllowAny]

    def get(self, request):
        roles = [role for role, _ in User.ROLE_CHOICES]
        return Response({"roles": roles}, status=status.HTTP_200_OK)


# =====================================================
# ✅ 7. USER LIST (Admin Only)
# =====================================================
class UserListView(generics.ListAPIView):
    """List all users (Admins only)."""
    queryset = User.objects.all().order_by("emp_id")
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "emp_id", "email", "first_name", "last_name", "status"]
    ordering_fields = ["emp_id", "username", "joining_date"]

    def get_queryset(self):
        """Filter users by status or department."""
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        department_param = self.request.query_params.get("department")

        if status_param:
            qs = qs.filter(status__iexact=status_param)
        if department_param:
            qs = qs.filter(department__name__icontains=department_param)
        return qs

    def list(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) == "Admin"):
            return Response(
                {"error": "Access denied. Admins only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)


# =====================================================
# ✅ 8. ADMIN RESET PASSWORD
# =====================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def reset_password(request):
    """
    Admins can reset any user's password.
    Generates a new temporary password and sets force_password_change=True.
    """
    emp_id = request.data.get("emp_id")
    if not emp_id:
        return Response({"error": "emp_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(emp_id=emp_id)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    new_password = get_random_string(
        length=12,
        allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+"
    )

    user.set_password(new_password)
    user.force_password_change = True
    user.save(update_fields=["password", "force_password_change"])

    return Response(
        {
            "message": f"✅ Password reset successfully for {user.emp_id}.",
            "username": user.username,
            "temp_password": new_password,
            "force_password_change": True,
        },
        status=status.HTTP_200_OK,
    )
