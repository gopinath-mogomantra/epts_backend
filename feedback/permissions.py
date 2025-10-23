# ===============================================
# feedback/permissions.py
# ===============================================
from rest_framework import permissions


# ===========================================================
# IsAdminOrManager
# ===========================================================
class IsAdminOrManager(permissions.BasePermission):
    """
    Allows access only to:
    - Superusers
    - Admins
    - Managers

    Used for most feedback endpoints to restrict create/update/delete
    to managerial roles while still allowing authenticated employees
    to view (if viewset allows it).
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        user_role = getattr(user, "role", "")
        return user.is_superuser or user_role in ("Admin", "Manager")


# ===========================================================
# IsCreatorOrAdmin
# ===========================================================
class IsCreatorOrAdmin(permissions.BasePermission):
    """
    Object-level permission:
    - Admins and Superusers: full access
    - Creator (created_by): can update/delete own feedback
    - Others: read-only (GET, HEAD, OPTIONS)

    Example use: Manager feedback or client feedback updates.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        # Admins and superusers always have full access
        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return True

        # Allow creator to modify their own feedback
        if hasattr(obj, "created_by") and obj.created_by == user:
            return True

        # Employees and others can only view (read-only)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Deny unsafe actions for all others
        return False
