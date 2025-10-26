# ===========================================================
# users/urls.py (Final — Frontend & API Aligned)
# ===========================================================
# Routes for:
# - Authentication (JWT Login, Refresh)
# - User Registration & Profile
# - Password Management (Change & Reset)
# - Role Listing & User Directory
# - Admin Delete User by emp_id
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
    UserDetailView,  # ✅ Added for Admin delete-by-emp_id
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
    path("<str:emp_id>/", UserDetailView.as_view(), name="user-detail"),  # ✅ New Admin Delete API

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
