# ===============================================
# users/views.py
# ===============================================
# Handles:
# 1. JWT Authentication (Login, Token Refresh)
# 2. User Registration (with optional auto password)
# 3. Profile Retrieval
# 4. Password Change
# 5. Role Listing
# 6. Admin-only: List All Users
# ===============================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
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
    Authenticates users using email/password and returns JWT tokens.
    """
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


# =====================================================
# ✅ 2. REFRESH TOKEN API
# =====================================================
class RefreshTokenView(TokenRefreshView):
    permission_classes = (AllowAny,)


# =====================================================
# ✅ 3. USER REGISTRATION API (Admin Only)
# =====================================================
class RegisterView(generics.CreateAPIView):
    """
    Admins or Superusers can register new users (employees/managers).
    Auto-generates a password if not provided.
    """
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        user = request.user

        # 🔐 Allow only Admins or Superusers to register new users
        if not (user.is_superuser or user.role == "Admin"):
            return Response(
                {"error": "Only Admins or Superusers can create new users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_user = serializer.save()

        return Response(
            {
                "message": "User registered successfully.",
                "user": ProfileSerializer(new_user).data,
            },
            status=status.HTTP_201_CREATED,
        )


# =====================================================
# ✅ 4. USER PROFILE API
# =====================================================
class ProfileView(APIView):
    """
    Retrieve profile details of the currently logged-in user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ✅ Safety checks
        if not user.is_active:
            return Response({"error": "Your account is inactive."}, status=403)

        serializer = ProfileSerializer(user)
        return Response(serializer.data, status=200)


# =====================================================
# ✅ 5. CHANGE PASSWORD API
# =====================================================
class ChangePasswordView(generics.UpdateAPIView):
    """
    Allow any logged-in user to change their password.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password updated successfully."}, status=200)


# =====================================================
# ✅ 6. ROLE LIST API
# =====================================================
class RoleListView(APIView):
    """
    Returns list of available roles.
    Used by frontend dropdowns (Admin, Manager, Employee).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = ["Admin", "Manager", "Employee"]
        return Response({"roles": roles}, status=200)


# =====================================================
# ✅ 7. ADMIN-ONLY: USER LIST API
# =====================================================
class UserListView(generics.ListAPIView):
    """
    Lists all registered users (Admins only).
    """
    queryset = User.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        # Restrict to Admins or Superusers
        if not (request.user.is_superuser or request.user.role == "Admin"):
            return Response({"error": "Access denied. Admins only."}, status=403)

        return super().list(request, *args, **kwargs)
