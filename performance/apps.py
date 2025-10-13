# ===============================================
# performance/apps.py
# ===============================================
# This file defines the configuration class for
# the 'performance' app. Django automatically
# detects and loads it when the app is added to
# INSTALLED_APPS in settings.py.
# ===============================================

from django.apps import AppConfig


class PerformanceConfig(AppConfig):
    """
    AppConfig for the 'performance' module.
    Helps Django identify and initialize the app.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'performance'
    verbose_name = 'Employee Performance Management'
