# feedback/permissions.py
from rest_framework import permissions


class IsAdminOrManager(permissions.BasePermission):
    """
    Permission class allowing access only to Admins, Managers, or Superusers.

    This assumes that the User model has a `role` field
    with possible values: "Admin", "Manager", or "Employee".
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Allow Superusers, Admins, and Managers
        return user.is_superuser or getattr(user, "role", "") in ["Admin", "Manager"]


class IsCreatorOrAdmin(permissions.BasePermission):
    """
    Permission class allowing modifications only by:
    - The user who created the object (`created_by`)
    - Or an Admin / Superuser.

    Employees can be allowed read-only access (GET, HEAD, OPTIONS)
    if required by future requirements.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Block anonymous users
        if not user or not user.is_authenticated:
            return False

        # Admins and superusers always have full access
        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return True

        # Allow the creator to modify their own records
        if hasattr(obj, "created_by") and obj.created_by == user:
            return True

        # Optional: allow read-only access for others
        if request.method in permissions.SAFE_METHODS:
            return True

        # Deny others for unsafe methods (POST, PUT, DELETE)
        return False
