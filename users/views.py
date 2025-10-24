# ===============================================
# users/views.py  (Updated / Fixed - Combined ChangePasswordView)
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
    Single endpoint to handle both:
    1) First-time password change (user has temp password -> provide username + old_password)
    2) Authenticated password change (user sends Bearer token)
    Use:
      POST /api/users/change-password/
    Payload (first-time):
      {
        "username": "EMP0001",
        "old_password": "tempPass123",
        "new_password": "NewStrongPass@123",
        "confirm_password": "NewStrongPass@123"
      }
    Payload (authenticated):
      {
        "old_password": "currentPass",
        "new_password": "NewStrongPass@123",
        "confirm_password": "NewStrongPass@123"
      }
    """
    permission_classes = [AllowAny]  # we will handle auth logic internally

    def post(self, request, *args, **kwargs):
        """
        Accepts either:
        - username + old_password (useful for first-time password reset when force_password_change=True), OR
        - Authorization: Bearer <token> header (authenticated user).
        """
        username = request.data.get("username")
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        # Basic validation for new passwords
        if not new_password or not confirm_password:
            return Response({"detail": "New password and confirm password are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"detail": "New passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        user = None

        # Case A: username + old_password provided -> try to authenticate (first-time or username-based change)
        if username and old_password:
            user = authenticate(username=username, password=old_password)
            if not user:
                return Response({"detail": "Invalid username or old password."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Case B: try to use authenticated user via token
            if request.user and request.user.is_authenticated:
                user = request.user
                # For safety, require old_password in authenticated flow as well (optional, but recommended)
                # If you want to allow changing without providing old_password (e.g., admin forced flow), you can adjust here.
                if not old_password:
                    return Response({"detail": "Old password is required for authenticated password change."},
                                    status=status.HTTP_400_BAD_REQUEST)
                if not user.check_password(old_password):
                    return Response({"detail": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # No username/old_password and no valid token
                return Response({"detail": "Authentication credentials were not provided."},
                                status=status.HTTP_401_UNAUTHORIZED)

        # At this point 'user' is valid
        user.set_password(new_password)
        # Clear force_password_change flag (covers first-time flow)
        user.force_password_change = False
        user.save(update_fields=["password", "force_password_change"])

        return Response({"message": "Password changed successfully!"}, status=status.HTTP_200_OK)


class ProfileView(APIView):
    """Return current user's profile info."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================
# ✅ 5. ROLE LIST
# =====================================================
class RoleListView(APIView):
    """Return available user roles."""
    permission_classes = [AllowAny]

    def get(self, request):
        roles = [role for role, _ in User.ROLE_CHOICES]
        return Response({"roles": roles}, status=status.HTTP_200_OK)


# =====================================================
# ✅ 6. USER LIST (Admin Only)
# =====================================================
class UserListView(generics.ListAPIView):
    """List all users (Admins only)."""
    queryset = User.objects.all().order_by("emp_id")
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "emp_id", "email", "first_name", "last_name"]
    ordering_fields = ["emp_id", "username"]

    def list(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) == "Admin"):
            return Response(
                {"error": "Access denied. Admins only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)


# =====================================================
# ✅ 7. ADMIN RESET PASSWORD
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
