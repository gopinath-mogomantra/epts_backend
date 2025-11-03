# ===========================================================
# feedback/permissions.py (Enhanced)
# ===========================================================
"""
Enhanced permission classes for feedback module.
"""

from rest_framework import permissions
import logging

logger = logging.getLogger(__name__)


class IsAdminOrManager(permissions.BasePermission):
    """
    Grant access to Admins and Managers only.
    """
    message = "You must be an Admin or Manager to perform this action."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        role = getattr(user, "role", "")
        return user.is_superuser or role in ("Admin", "Manager")


class IsCreatorOrAdmin(permissions.BasePermission):
    """
    Object-level permission:
    - Admins: full access
    - Creator: can modify their own feedback
    - Others: read-only
    """
    message = "You do not have permission to modify this feedback."

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Read-only for safe methods
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Admins have full access
        if user.is_superuser or getattr(user, "role", "") == "Admin":
            return True
        
        # Creator can modify
        if hasattr(obj, "created_by") and obj.created_by == user:
            return True
        
        return False


class IsEmployeeOrAdminOrManager(permissions.BasePermission):
    """
    Allow employees to view their own feedback,
    Admins and Managers to view all feedback.
    """
    message = "You don't have permission to access this feedback."

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if not user or not user.is_authenticated:
            return False
        
        # Admins and Managers can access all
        role = getattr(user, "role", "")
        if user.is_superuser or role in ("Admin", "Manager"):
            return True
        
        # Employees can only access their own public feedback
        if obj.employee and obj.employee.user == user:
            if request.method in permissions.SAFE_METHODS:
                # Can view if public or they're the employee
                return True
            # Can modify acknowledgment/response
            return view.action in ['acknowledge', 'complete_action']
        
        return False