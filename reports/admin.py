# reports/admin.py
from django.contrib import admin
from .models import CachedReport

@admin.register(CachedReport)
class CachedReportAdmin(admin.ModelAdmin):
    list_display = ("report_type", "year", "week_number", "month", "generated_at")
