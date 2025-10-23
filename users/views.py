# ===============================================
# users/views.py (Final Version)
# ===============================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.crypto import get_random_string

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
# ✅ 3. USER REGISTRATION (Admin / Superuser Only)
# =====================================================
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) == "Admin"):
            return Response(
                {"error": "Only Admins or Superusers can create new users."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_user = serializer.save()

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
# ✅ 4. USER PROFILE API (Self)
# =====================================================
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_active:
            return Response(
                {"error": "Your account is inactive."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = ProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


# =====================================================
# ✅ 5. CHANGE PASSWORD API
# =====================================================
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def put(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = request.user
        old_password = serializer.validated_data.get("old_password")
        new_password = serializer.validated_data.get("new_password")

        if not user.check_password(old_password):
            return Response({"error": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.force_password_change = False
        user.save()

        return Response({"message": "Password changed successfully!"}, status=status.HTTP_200_OK)


# =====================================================
# ✅ 6. ROLE LIST API
# =====================================================
class RoleListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        roles = [r[0] for r in User.ROLE_CHOICES]
        return Response({"roles": roles}, status=status.HTTP_200_OK)


# =====================================================
# ✅ 7. ADMIN-ONLY: USER LIST API
# =====================================================
class UserListView(generics.ListAPIView):
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
# ✅ 8. ADMIN RESET PASSWORD API
# =====================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def reset_password(request):
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
    user.save()

    return Response({
        "message": f"Password reset successfully for {user.emp_id}.",
        "username": user.username,
        "temp_password": new_password,
        "force_password_change": True
    }, status=status.HTTP_200_OK)
