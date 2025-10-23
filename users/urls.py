# ===========================================================
# users/urls.py
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

urlpatterns = [
    path("login/", ObtainTokenPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token_refresh"),
    path("register/", RegisterView.as_view(), name="register"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("roles/", RoleListView.as_view(), name="roles"),
    path("list/", UserListView.as_view(), name="user-list"),
    path("reset-password/", reset_password, name="reset-password"),
]
