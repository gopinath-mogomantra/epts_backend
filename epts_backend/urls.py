from django.contrib import admin
from django.urls import path, include, re_path
from django.http import JsonResponse
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from django.conf import settings
from django.conf.urls.static import static

# ✅ Define the home view BEFORE urlpatterns
def home(request):
    return JsonResponse({
        "status": "ok",
        "message": "EPTS Backend is running successfully 🚀"
    })

# Swagger schema setup
schema_view = get_schema_view(
    openapi.Info(
        title="EPTS API",
        default_version='v1',
        description="Employee Performance Tracking System API documentation",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@epts.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # ✅ Root URL returns JSON confirmation
    path('', home),

    # Admin panel
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')), 

    # API modules  
    path('api/employee/', include('employee.urls')),
    path('api/performance/', include('performance.urls')),

    # Swagger and Redoc routes
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Serve media/static files in debug
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

