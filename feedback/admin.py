# feedback/admin.py
from django.contrib import admin
from .models import GeneralFeedback, ManagerFeedback, ClientFeedback

@admin.register(GeneralFeedback)
class GeneralFeedbackAdmin(admin.ModelAdmin):
    list_display = ("employee", "rating", "created_by", "feedback_date", "created_at")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "feedback_text")
    list_filter = ("rating", "feedback_date", "department")


@admin.register(ManagerFeedback)
class ManagerFeedbackAdmin(admin.ModelAdmin):
    list_display = ("employee", "rating", "manager_name", "created_by", "feedback_date")
    search_fields = ("employee__user__first_name", "manager_name", "feedback_text")
    list_filter = ("rating", "feedback_date", "department")


@admin.register(ClientFeedback)
class ClientFeedbackAdmin(admin.ModelAdmin):
    list_display = ("employee", "client_name", "rating", "created_by", "feedback_date")
    search_fields = ("client_name", "employee__user__first_name", "feedback_text")
    list_filter = ("rating", "feedback_date", "department")
