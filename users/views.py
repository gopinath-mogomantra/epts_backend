# ===============================================
# users/views.py
# ===============================================
# Handles:
# 1. JWT Authentication (Login, Token Refresh)
# 2. User Registration
# 3. Profile Retrieval
# 4. Password Change
# 5. Role Listing
# ===============================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from .models import CustomUser
from django.contrib.auth.models import User
from .serializers import ChangePasswordSerializer

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
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer

# =====================================================
# ✅ 2. REFRESH TOKEN API
# =====================================================
class RefreshTokenView(TokenRefreshView):
    permission_classes = (AllowAny,)

# =====================================================
# ✅ 3. USER REGISTRATION API
# =====================================================
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "message": "User registered successfully.",
            "user": ProfileSerializer(user).data
        }, status=status.HTTP_201_CREATED)

# =====================================================
# ✅ 4. USER PROFILE API
# =====================================================
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    


class UserListView(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAdminUser]

# =====================================================
# ✅ 5. CHANGE PASSWORD API
# =====================================================
class ChangePasswordView(generics.UpdateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def get_object(self):
        return self.request.user
    

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = self.get_object()
        serializer.update(user, serializer.validated_data)
        return Response({"message": "Password updated successfully."}, status=status.HTTP_200_OK)

# =====================================================
# ✅ 6. ROLE LIST API
# =====================================================
class RoleListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get all distinct role names (Admin, Manager, Employee)
        roles = (
            User.objects.filter(role__isnull=False)
            .values_list('role__name', flat=True)
            .distinct()
        )
        return Response(list(roles), status=status.HTTP_200_OK)
