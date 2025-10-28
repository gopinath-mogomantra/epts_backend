# ===========================================================
# users/urls.py ✅ (Frontend-Aligned & Production-Ready)
# Employee Performance Tracking System (EPTS)
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
    UserDetailView,
)

# ===========================================================
# APP NAMESPACE (for include() usage and Swagger clarity)
# ===========================================================
app_name = "users"

# ===========================================================
# ROUTES SUMMARY
# ===========================================================
# 1. /api/users/login/                  → JWT Login (emp_id or username)
# 2. /api/users/token/refresh/          → Refresh JWT token
# 3. /api/users/register/               → Register new user (Admin / Manager)
# 4. /api/users/profile/                → Get or Update logged-in user profile
# 5. /api/users/change-password/        → Change current user password
# 6. /api/users/roles/                  → Get available roles
# 7. /api/users/list/                   → Paginated user list (Admin only)
# 8. /api/users/reset-password/         → Admin resets user password
# 9. /api/users/<emp_id>/               → Admin view/update/delete specific user
# ===========================================================

urlpatterns = [
    # 🔐 Authentication
    path("login/", ObtainTokenPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token_refresh"),

    # 🧑‍💻 Registration & Profile Management
    path("register/", RegisterView.as_view(), name="user_register"),
    path("profile/", ProfileView.as_view(), name="user_profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),

    # 🏷️ Roles & Directory
    path("roles/", RoleListView.as_view(), name="role_list"),
    path("list/", UserListView.as_view(), name="user_list"),

    # 🔁 Admin Utilities
    path("reset-password/", reset_password, name="reset_password"),
    path("<str:emp_id>/", UserDetailView.as_view(), name="user_detail"),
]
