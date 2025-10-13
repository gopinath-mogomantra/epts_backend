from django.urls import path
from rest_framework_simplejwt.views import TokenVerifyView
from .views import (
    ObtainTokenPairView,
    RefreshTokenView,
    RegisterView,
    ProfileView,
    ChangePasswordView,
    RoleListView,
    UserListView,  # ✅ Add this import
)

urlpatterns = [
    # JWT Authentication Endpoints
    path('token/', ObtainTokenPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', RefreshTokenView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # Registration and Profile
    path('register/', RegisterView.as_view(), name='user_register'),
    path('me/', ProfileView.as_view(), name='user_profile'),

    # Change Password
    path('me/change-password/', ChangePasswordView.as_view(), name='change_password'),

    # Roles List (For Admin Role Management)
    path('roles/', RoleListView.as_view(), name='role_list'),

    # User List (For Admin to view all users)
    path('users/', UserListView.as_view(), name='user_list'),
]
