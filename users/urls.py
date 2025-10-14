# ===============================================
# users/urls.py
# ===============================================
# Maps all user-related API endpoints:
# - JWT Authentication
# - Registration
# - Profile
# - Password Change
# - Role List
# - User List (Admin-only)
# ===============================================

from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView
from .views import (
    ObtainTokenPairView,
    RefreshTokenView,
    RegisterView,
    ProfileView,
    ChangePasswordView,
    RoleListView,
    UserListView,
)

app_name = "users"  # ✅ Recommended for namespacing in include()

urlpatterns = [
    # 🔐 JWT Authentication
    path("token/", ObtainTokenPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # 👤 Registration & Profile
    path("register/", RegisterView.as_view(), name="user_register"),
    path("me/", ProfileView.as_view(), name="user_profile"),

    # 🔑 Password Management
    path("me/change-password/", ChangePasswordView.as_view(), name="change_password"),

    # 🧩 Role List (for dropdowns in frontend)
    path("roles/", RoleListView.as_view(), name="role_list"),

    # 📋 Admin-only: User List
    path("list/", UserListView.as_view(), name="user_list"),
]
