from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


# ===========================================================
# IsAdminOrManager
# ===========================================================
class IsAdminOrManager(permissions.BasePermission):
    """
    Global permission class:
    ✅ Grants full access to:
        - Superusers
        - Users with role = 'Admin' or 'Manager'
    ❌ Denies for:
        - Employees or unauthenticated users
    """

    message = "You must be an Admin or Manager to perform this action."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            logger.debug("Access denied: unauthenticated user.")
            return False

        role = getattr(user, "role", "")
        is_allowed = user.is_superuser or role in ("Admin", "Manager")

        if not is_allowed:
            logger.debug(f"Access denied for role '{role}' on {view.__class__.__name__}")
        return is_allowed


# ===========================================================
# IsCreatorOrAdmin
# ===========================================================
class IsCreatorOrAdmin(permissions.BasePermission):
    """
    Object-level permission class:
    ✅ Admins/Superusers: unrestricted
    ✅ Creator: can update/delete their own feedback
    ✅ Others: read-only (GET, HEAD, OPTIONS)
    """

    message = "You do not have permission to modify this feedback."

    def has_object_permission(self, request, view, obj):
        user = request.user

        if not user or not user.is_authenticated:
            logger.debug("Access denied: unauthenticated object access.")
            return False

        # Always allow safe read-only methods
        if request.method in permissions.SAFE_METHODS:
            return True

        # Admins and superusers have full access
        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return True

        # Allow creator to modify their own feedback
        if hasattr(obj, "created_by") and obj.created_by == user:
            return True

        logger.debug(f"Permission denied for user {user.username} on {obj.__class__.__name__}")
        return False
