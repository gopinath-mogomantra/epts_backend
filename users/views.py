# ===============================================
# users/views.py
# ===============================================
# Handles:
# 1. JWT Authentication (Login, Token Refresh)
# 2. Admin-based User Registration
# 3. Profile Retrieval (Self)
# 4. Password Change
# 5. Role Listing
# 6. Admin-Only: User List
# ===============================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from django.utils import timezone

from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    ChangePasswordSerializer,
    ProfileSerializer,
)

User = get_user_model()


# =====================================================
# ✅ 1. LOGIN API (JWT Token Obtain View)
# =====================================================
class ObtainTokenPairView(TokenObtainPairView):
    """
    Authenticates users using username/password and returns JWT tokens
    along with role and employee info.
    """
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


# =====================================================
# ✅ 2. REFRESH TOKEN API
# =====================================================
class RefreshTokenView(TokenRefreshView):
    """
    Refreshes expired access tokens using a valid refresh token.
    """
    permission_classes = (AllowAny,)


# =====================================================
# ✅ 3. USER REGISTRATION (Admin / Superuser Only)
# =====================================================
class RegisterView(generics.CreateAPIView):
    """
    Allows Admin or Superuser to register new users.
    Automatically creates a user with optional password.
    """
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        current_user = request.user

        # Restrict to Admins or Superusers only
        if not (current_user.is_superuser or getattr(current_user, "role", None) == "Admin"):
            return Response(
                {"error": "Only Admins or Superusers can create new users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_user = serializer.save()

        # Auto-generate Employee joining date if not provided
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
# ✅ 4. USER PROFILE API
# =====================================================
class ProfileView(APIView):
    """
    Retrieves the profile details of the currently logged-in user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_active:
            return Response({"error": "Your account is inactive."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================
# ✅ 5. CHANGE PASSWORD API
# =====================================================
class ChangePasswordView(generics.UpdateAPIView):
    """
    Allows authenticated users to change their password.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "🔐 Password updated successfully."}, status=status.HTTP_200_OK)


# =====================================================
# ✅ 6. ROLE LIST API
# =====================================================
class RoleListView(APIView):
    """
    Returns the list of available roles.
    (Useful for frontend dropdowns in user creation forms.)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = ["Admin", "Manager", "Employee"]
        return Response({"roles": roles}, status=status.HTTP_200_OK)


# =====================================================
# ✅ 7. ADMIN-ONLY: USER LIST API
# =====================================================
class UserListView(generics.ListAPIView):
    """
    Lists all registered users (Admins / Superusers only).
    """
    queryset = User.objects.all().order_by("emp_id")
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        # Restrict to Admins or Superusers
        if not (request.user.is_superuser or getattr(request.user, "role", None) == "Admin"):
            return Response({"error": "Access denied. Admins only."}, status=status.HTTP_403_FORBIDDEN)

        return super().list(request, *args, **kwargs)
