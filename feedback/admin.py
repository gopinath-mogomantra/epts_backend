from django.contrib import admin
from django.http import HttpResponse
import csv
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback


# ===========================================================
# Base Feedback Admin (Common Functionality)
# ===========================================================
class BaseFeedbackAdmin(admin.ModelAdmin):
    """Base admin configuration reused by all feedback models."""

    list_per_page = 20
    date_hierarchy = "feedback_date"
    readonly_fields = ("created_by", "created_at", "updated_at")
    list_filter = ("rating", "feedback_date", "department", "visibility")
    search_fields = (
        "employee__user__emp_id",
        "employee__user__first_name",
        "employee__user__last_name",
        "feedback_text",
    )
    ordering = ("-feedback_date",)
    actions = ["export_as_csv"]

    fieldsets = (
        ("Feedback Info", {
            "fields": ("employee", "department", "feedback_text", "remarks", "rating", "visibility"),
        }),
        ("Metadata", {
            "fields": ("created_by", "feedback_date", "created_at", "updated_at"),
        }),
    )

    # -------------------------------------------------------
    # Display Helpers
    # -------------------------------------------------------
    def get_emp_id(self, obj):
        return getattr(obj.employee.user, "emp_id", "-")
    get_emp_id.short_description = "Emp ID"

    def get_employee_name(self, obj):
        if obj.employee and obj.employee.user:
            u = obj.employee.user
            return f"{u.first_name} {u.last_name}".strip()
        return "-"
    get_employee_name.short_description = "Employee Name"

    # -------------------------------------------------------
    # Export to CSV Action
    # -------------------------------------------------------
    def export_as_csv(self, request, queryset):
        """Export selected feedback entries to a CSV file."""
        meta = self.model._meta
        field_names = ["Emp ID", "Employee Name", "Department", "Rating", "Feedback Date", "Feedback Text"]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename={meta.verbose_name_plural.lower()}.csv'
        writer = csv.writer(response)
        writer.writerow(field_names)

        for obj in queryset:
            writer.writerow([
                getattr(obj.employee.user, "emp_id", "-"),
                f"{obj.employee.user.first_name} {obj.employee.user.last_name}".strip()
                if obj.employee and obj.employee.user else "-",
                getattr(obj.department, "name", "-"),
                obj.rating,
                obj.feedback_date,
                obj.feedback_text,
            ])

        return response
    export_as_csv.short_description = "Export selected feedbacks as CSV"


# ===========================================================
# General Feedback Admin
# ===========================================================
@admin.register(GeneralFeedback)
class GeneralFeedbackAdmin(BaseFeedbackAdmin):
    """Admin configuration for General Feedback."""
    list_display = ("get_emp_id", "get_employee_name", "rating", "created_by", "feedback_date", "created_at")


# ===========================================================
# Manager Feedback Admin
# ===========================================================
@admin.register(ManagerFeedback)
class ManagerFeedbackAdmin(BaseFeedbackAdmin):
    """Admin configuration for Manager Feedback."""
    list_display = (
        "get_emp_id",
        "get_employee_name",
        "manager_name",
        "rating",
        "created_by",
        "feedback_date",
    )
    search_fields = BaseFeedbackAdmin.search_fields + ("manager_name",)


# ===========================================================
# Client Feedback Admin
# ===========================================================
@admin.register(ClientFeedback)
class ClientFeedbackAdmin(BaseFeedbackAdmin):
    """Admin configuration for Client Feedback."""
    list_display = (
        "get_emp_id",
        "get_employee_name",
        "client_name",
        "rating",
        "created_by",
        "feedback_date",
    )
    search_fields = BaseFeedbackAdmin.search_fields + ("client_name",)
