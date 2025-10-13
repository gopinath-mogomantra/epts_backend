# ===============================================
# performance/admin.py
# ===============================================
# Registers PerformanceEvaluation model with Django Admin.
# Enables easy management, search, and filtering of records.
# ===============================================

from django.contrib import admin
from .models import PerformanceEvaluation


@admin.register(PerformanceEvaluation)
class PerformanceEvaluationAdmin(admin.ModelAdmin):
    """
    Admin configuration for Performance Evaluation records.
    """
    # Fields displayed in the list page of the admin
    list_display = (
        'id', 'emp', 'department', 'manager', 'review_date',
        'evaluation_period', 'total_score'
    )

    # Add quick search functionality
    search_fields = (
        'emp__first_name', 'emp__last_name', 'emp__emp_id',
        'department__name', 'manager__first_name', 'manager__last_name'
    )

    # Filters on the right sidebar for easy record grouping
    list_filter = ('department', 'manager', 'evaluation_period')

    # Make certain fields read-only
    readonly_fields = ('total_score', 'created_at', 'updated_at')

    # Sort records by most recent review date
    ordering = ('-review_date',)

    # Customize how the model appears in the admin panel
    list_per_page = 20
    date_hierarchy = 'review_date'

    # Field grouping inside the record form
    fieldsets = (
        ('Employee & Review Info', {
            'fields': ('emp', 'department', 'manager', 'review_date', 'evaluation_period')
        }),
        ('Performance Metrics', {
            'fields': (
                'communication_skills', 'multitasking', 'team_skills', 'technical_skills',
                'job_knowledge', 'productivity', 'creativity', 'work_quality',
                'professionalism', 'work_consistency', 'attitude', 'cooperation',
                'dependability', 'attendance', 'punctuality'
            )
        }),
        ('Summary', {
            'fields': ('total_score', 'remarks', 'created_at', 'updated_at')
        }),
    )

    # Automatically refresh total_score when saving from admin panel
    def save_model(self, request, obj, form, change):
        obj.save()  # Model’s save() will recalculate total_score
        super().save_model(request, obj, form, change)
