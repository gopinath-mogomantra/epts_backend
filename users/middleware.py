from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.contrib.auth.models import AnonymousUser


class RoleBasedAccessMiddleware(MiddlewareMixin):
    """
    Custom middleware for enforcing role-based access control (RBAC).
    Validates JWT token from Authorization header and checks user role.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip admin site, static/media routes
        if request.path.startswith('/admin') or request.path.startswith('/static') or request.path.startswith('/media'):
            return None

        # Try to authenticate user using JWT
        jwt_auth = JWTAuthentication()
        user, _ = None, None
        try:
            user, _ = jwt_auth.authenticate(request)
        except Exception:
            pass

        # If no valid token, set as anonymous
        if user is None:
            request.user = AnonymousUser()
        else:
            request.user = user

        # Optional: Apply RBAC rules based on URL path
        if request.user and request.user.is_authenticated:
            # Example: Restrict endpoints based on role
            if request.path.startswith('/api/admin/') and not request.user.is_admin():
                return JsonResponse(
                    {"detail": "Access denied. Admin role required."},
                    status=403
                )

            if request.path.startswith('/api/manager/') and not (request.user.is_admin() or request.user.is_manager()):
                return JsonResponse(
                    {"detail": "Access denied. Manager or Admin role required."},
                    status=403
                )

            if request.path.startswith('/api/employee/') and not request.user.is_employee():
                return JsonResponse(
                    {"detail": "Access denied. Employee role required."},
                    status=403
                )

        return None
