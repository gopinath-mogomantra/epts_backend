# ===========================================================
# users/views.py (Final — Admin CRUD Ready & API Validation)
# ===========================================================

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import generics, status, filters, permissions
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


# ===========================================================
# ✅ 1. LOGIN (JWT Authentication)
# ===========================================================
class ObtainTokenPairView(TokenObtainPairView):
    """Authenticate user via emp_id or username."""
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


# ===========================================================
# ✅ 2. REFRESH TOKEN
# ===========================================================
class RefreshTokenView(TokenRefreshView):
    """Refresh access token using refresh token."""
    permission_classes = [AllowAny]


# ===========================================================
# ✅ 3. REGISTER USER (Admin Only — Single + Bulk Create)
# ===========================================================
class RegisterView(generics.CreateAPIView):
    """
    Allows Admins/Superusers to register:
    - Single user → POST single JSON object
    - Multiple users → POST JSON array
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

        data = request.data
        many = isinstance(data, list)
        serializer = self.get_serializer(data=data, many=many)
        serializer.is_valid(raise_exception=True)
        new_users = serializer.save()

        # ✅ Set joining_date automatically if missing
        if many:
            for user in new_users:
                if not getattr(user, "joining_date", None):
                    user.joining_date = timezone.now().date()
                    user.save(update_fields=["joining_date"])
        else:
            if not getattr(new_users, "joining_date", None):
                new_users.joining_date = timezone.now().date()
                new_users.save(update_fields=["joining_date"])

        # ✅ Build response
        if many:
            users_data = [
                {
                    "emp_id": user.emp_id,
                    "username": user.username,
                    "email": user.email,
                    "temp_password": getattr(user, "temp_password", None),
                }
                for user in new_users
            ]
            return Response(
                {"message": f"{len(new_users)} users created successfully!", "users": users_data},
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                {
                    "message": "✅ User registered successfully!",
                    "user": ProfileSerializer(new_users).data,
                },
                status=status.HTTP_201_CREATED,
            )


# ===========================================================
# ✅ 4. CHANGE PASSWORD
# ===========================================================
class ChangePasswordView(APIView):
    """Handles password change (first login or normal)."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not new_password or not confirm_password:
            return Response(
                {"detail": "New password and confirm password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if new_password != confirm_password:
            return Response({"detail": "New passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        user = None

        if username and old_password:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
            if not user.check_password(old_password):
                return Response({"detail": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        elif request.user and request.user.is_authenticated:
            user = request.user
            if not old_password:
                return Response({"detail": "Old password is required."}, status=status.HTTP_400_BAD_REQUEST)
            if not user.check_password(old_password):
                return Response({"detail": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user.set_password(new_password)
        if hasattr(user, "force_password_change"):
            user.force_password_change = False
        user.save(update_fields=["password", "force_password_change"] if hasattr(user, "force_password_change") else ["password"])

        return Response({"message": "✅ Password changed successfully!"}, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 5. PROFILE API (GET + PATCH for self-update)
# ===========================================================
class ProfileView(APIView):
    """
    GET: Fetch logged-in user's profile
    PATCH: Allow users to update limited fields (first_name, last_name, phone, email)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        user = request.user
        data = request.data
        editable_fields = ["first_name", "last_name", "email", "phone"]

        for field, value in data.items():
            if field in editable_fields:
                setattr(user, field, value)

        user.save(update_fields=[f for f in data.keys() if f in editable_fields])

        serializer = ProfileSerializer(user)
        return Response(
            {"message": "✅ Profile updated successfully!", "user": serializer.data},
            status=status.HTTP_200_OK,
        )


# ===========================================================
# ✅ 6. ROLE LIST
# ===========================================================
class RoleListView(APIView):
    """Return available roles for dropdown."""
    permission_classes = [AllowAny]

    def get(self, request):
        roles = [role for role, _ in User.ROLE_CHOICES]
        return Response({"roles": roles}, status=status.HTTP_200_OK)


# ===========================================================
# ✅ 7. USER LIST (Admin Only)
# ===========================================================
class UserListView(generics.ListAPIView):
    """Lists all users — visible to Admins only."""
    queryset = User.objects.all().order_by("emp_id")
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username", "emp_id", "email", "first_name", "last_name", "status"]
    ordering_fields = ["emp_id", "username", "joining_date"]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        dept_param = self.request.query_params.get("department")

        if status_param:
            qs = qs.filter(status__iexact=status_param)
        if dept_param:
            qs = qs.filter(department__name__icontains=dept_param)
        return qs

    def list(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or getattr(user, "role", None) == "Admin"):
            return Response({"error": "Access denied. Admins only."}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)


# ===========================================================
# ✅ 8. ADMIN RESET PASSWORD
# ===========================================================
@api_view(["POST"])
@permission_classes([IsAdminUser])
def reset_password(request):
    """Reset a user’s password (Admin only)."""
    emp_id = request.data.get("emp_id")
    if not emp_id:
        return Response({"error": "emp_id is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(emp_id=emp_id)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    new_password = get_random_string(length=10, allowed_chars="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*")
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


# ===========================================================
# ✅ 9. USER DETAIL (GET / PATCH / DELETE) — Admin Only
# ===========================================================
class UserDetailView(APIView):
    """
    Admins can:
    - GET: Fetch user by emp_id
    - PATCH: Update fields (phone, email, verification, etc.)
    - DELETE: Remove user safely
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, emp_id):
        try:
            return User.objects.get(emp_id=emp_id)
        except User.DoesNotExist:
            return None

    def get(self, request, emp_id):
        user = self.get_object(emp_id)
        if not user:
            return Response({"error": f"User with emp_id '{emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ProfileSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, emp_id):
        current_user = request.user
        if not (current_user.is_superuser or getattr(current_user, "role", None) == "Admin"):
            return Response({"error": "Access denied. Only Admins can update users."}, status=status.HTTP_403_FORBIDDEN)

        user = self.get_object(emp_id)
        if not user:
            return Response({"error": f"User with emp_id '{emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        editable_fields = ["first_name", "last_name", "email", "phone", "is_verified", "status", "department"]
        for field, value in request.data.items():
            if field in editable_fields:
                setattr(user, field, value)
        user.save(update_fields=[f for f in request.data.keys() if f in editable_fields])

        serializer = ProfileSerializer(user)
        return Response(
            {"message": f"✅ User '{emp_id}' updated successfully!", "user": serializer.data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, emp_id):
        current_user = request.user
        if not (current_user.is_superuser or getattr(current_user, "role", None) == "Admin"):
            return Response({"error": "Access denied. Only Admins can delete users."}, status=status.HTTP_403_FORBIDDEN)

        user = self.get_object(emp_id)
        if not user:
            return Response({"error": f"User with emp_id '{emp_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        if user == current_user:
            return Response({"error": "You cannot delete your own account."}, status=status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response({"message": f"✅ User '{emp_id}' deleted successfully."}, status=status.HTTP_200_OK)
