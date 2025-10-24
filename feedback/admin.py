# ===============================================
# feedback/admin.py (Final Verified Version)
# ===============================================
# Admin configuration for Feedback modules:
# General, Manager, and Client Feedback.
# ===============================================

from django.contrib import admin
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback


# =====================================================
# GENERAL FEEDBACK ADMIN
# =====================================================
@admin.register(GeneralFeedback)
class GeneralFeedbackAdmin(admin.ModelAdmin):
    """Admin configuration for general feedback."""
    list_display = ("get_emp_id", "get_employee_name", "rating", "created_by", "feedback_date", "created_at")
    search_fields = (
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__emp_id",
        "feedback_text",
    )
    list_filter = ("rating", "feedback_date", "department")
    ordering = ("-feedback_date",)

    def get_emp_id(self, obj):
        return getattr(obj.employee.user, "emp_id", "-")
    get_emp_id.short_description = "Emp ID"

    def get_employee_name(self, obj):
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"
    get_employee_name.short_description = "Employee Name"


# =====================================================
# MANAGER FEEDBACK ADMIN
# =====================================================
@admin.register(ManagerFeedback)
class ManagerFeedbackAdmin(admin.ModelAdmin):
    """Admin configuration for manager feedback."""
    list_display = ("get_emp_id", "get_employee_name", "manager_name", "rating", "created_by", "feedback_date")
    search_fields = (
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__emp_id",
        "manager_name",
        "feedback_text",
    )
    list_filter = ("rating", "feedback_date", "department")
    ordering = ("-feedback_date",)

    def get_emp_id(self, obj):
        return getattr(obj.employee.user, "emp_id", "-")
    get_emp_id.short_description = "Emp ID"

    def get_employee_name(self, obj):
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"
    get_employee_name.short_description = "Employee Name"


# =====================================================
# CLIENT FEEDBACK ADMIN
# =====================================================
@admin.register(ClientFeedback)
class ClientFeedbackAdmin(admin.ModelAdmin):
    """Admin configuration for client feedback."""
    list_display = ("get_emp_id", "get_employee_name", "client_name", "rating", "created_by", "feedback_date")
    search_fields = (
        "client_name",
        "employee__user__first_name",
        "employee__user__last_name",
        "employee__user__emp_id",
        "feedback_text",
    )
    list_filter = ("rating", "feedback_date", "department")
    ordering = ("-feedback_date",)

    def get_emp_id(self, obj):
        return getattr(obj.employee.user, "emp_id", "-")
    get_emp_id.short_description = "Emp ID"

    def get_employee_name(self, obj):
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"
    get_employee_name.short_description = "Employee Name"
