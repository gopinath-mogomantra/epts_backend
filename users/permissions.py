from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Allows access only to users with Admin role or superuser status.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin())


class IsManager(permissions.BasePermission):
    """
    Allows access to users with Manager or Admin roles.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_admin() or request.user.is_manager())
        )


class IsEmployee(permissions.BasePermission):
    """
    Allows access to users with Employee, Manager, or Admin roles.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_employee() or request.user.is_manager() or request.user.is_admin())
        )


class IsSelfOrAdmin(permissions.BasePermission):
    """
    Allow users to view or edit only their own data, unless user is Admin.
    """
    def has_object_permission(self, request, view, obj):
        # Allow access if the user is admin or the user is viewing/updating their own record
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_admin() or obj == request.user)
        )
