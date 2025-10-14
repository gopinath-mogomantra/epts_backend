# ===============================================
# users/urls.py
# ===============================================
# Maps all user-related API endpoints:
# - JWT Authentication (login, refresh, verify)
# - Registration (Admin-only)
# - Profile (Self)
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

app_name = "users"  # ✅ Namespacing for better clarity

urlpatterns = [
    # ---------------------------------------------------
    # 🔐 AUTHENTICATION ENDPOINTS
    # ---------------------------------------------------
    path("token/login/", ObtainTokenPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token_refresh"),
    path("token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # ---------------------------------------------------
    # 👤 USER MANAGEMENT
    # ---------------------------------------------------
    path("register/", RegisterView.as_view(), name="user_register"),      # Admin-only
    path("profile/", ProfileView.as_view(), name="user_profile"),         # Self profile

    # ---------------------------------------------------
    # 🔑 PASSWORD MANAGEMENT
    # ---------------------------------------------------
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),

    # ---------------------------------------------------
    # 🧩 ROLE LIST (Frontend dropdown helper)
    # ---------------------------------------------------
    path("roles/", RoleListView.as_view(), name="role_list"),

    # ---------------------------------------------------
    # 📋 ADMIN-ONLY USER LIST
    # ---------------------------------------------------
    path("list/", UserListView.as_view(), name="user_list"),
]
