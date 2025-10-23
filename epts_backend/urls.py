# epts_backend/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.shortcuts import render
from django.conf import settings
from django.conf.urls.static import static

from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions


# -------------------------------------------------------------------
# SIMPLE HOME VIEW (optional landing page)
# -------------------------------------------------------------------
def home(request):
    """Simple home endpoint for base URL /"""
    return render(request, "home.html")


# -------------------------------------------------------------------
# SWAGGER / REDOC DOCUMENTATION
# -------------------------------------------------------------------
schema_view = get_schema_view(
    openapi.Info(
        title="Employee Performance Tracking System (EPTS) API",
        default_version=getattr(settings, "VERSION", "v1"),
        description="Comprehensive API documentation for EPTS backend services.",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@epts.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

# -------------------------------------------------------------------
# URL ROUTES
# -------------------------------------------------------------------
urlpatterns = [
    # Root route
    path("", home, name="home"),

    # Django admin
    path("admin/", admin.site.urls),

    # App routes
    path("api/users/", include("users.urls")),
    path("api/employee/", include("employee.urls")),
    path("api/performance/", include("performance.urls")),
    path("api/feedback/", include("feedback.urls", namespace="feedback")),
    path("api/reports/", include("reports.urls", namespace="reports")),
    path("api/notifications/", include("notifications.urls", namespace="notifications")),
]

# -------------------------------------------------------------------
# Swagger / Redoc routes (only enabled in DEBUG mode)
# -------------------------------------------------------------------
if settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^swagger(?P<format>\.json|\.yaml)$",
            schema_view.without_ui(cache_timeout=0),
            name="schema-json",
        ),
        path(
            "swagger/",
            schema_view.with_ui("swagger", cache_timeout=0),
            name="schema-swagger-ui",
        ),
        path(
            "redoc/",
            schema_view.with_ui("redoc", cache_timeout=0),
            name="schema-redoc",
        ),
    ]

# -------------------------------------------------------------------
# STATIC & MEDIA FILES (dev only)
# -------------------------------------------------------------------
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
