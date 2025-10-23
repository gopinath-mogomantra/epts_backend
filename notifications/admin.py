from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "employee", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("employee__email", "employee__first_name", "message")
