# ===========================================================
# users/urls.py (Final Updated — Frontend & API Aligned)
# ===========================================================
# Routes for:
# - Authentication (JWT Login, Refresh)
# - User Registration & Profile
# - Password Management (Change & Reset)
# - Role Listing & User Directory
# ===========================================================

from django.urls import path
from .views import (
    ObtainTokenPairView,
    RefreshTokenView,
    RegisterView,
    ProfileView,
    ChangePasswordView,
    RoleListView,
    UserListView,
    reset_password,
)

app_name = "users"

urlpatterns = [
    # -------------------------------------------------------
    # 🔐 Authentication Endpoints
    # -------------------------------------------------------
    path("login/", ObtainTokenPairView.as_view(), name="login"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),

    # -------------------------------------------------------
    # 👤 User Management
    # -------------------------------------------------------
    path("register/", RegisterView.as_view(), name="register"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("list/", UserListView.as_view(), name="user-list"),

    # -------------------------------------------------------
    # 🔄 Password Management
    # -------------------------------------------------------
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("reset-password/", reset_password, name="reset-password"),

    # -------------------------------------------------------
    # ⚙️ Roles
    # -------------------------------------------------------
    path("roles/", RoleListView.as_view(), name="roles"),
]
