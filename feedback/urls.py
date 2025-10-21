# feedback/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GeneralFeedbackViewSet,
    ManagerFeedbackViewSet,
    ClientFeedbackViewSet,
)

app_name = "feedback"

# ----------------------------------------------
# Router Configuration
# ----------------------------------------------
router = DefaultRouter()

# Register viewsets with clear basename prefixes
router.register(r"general-feedback", GeneralFeedbackViewSet, basename="general-feedback")
router.register(r"manager-feedback", ManagerFeedbackViewSet, basename="manager-feedback")
router.register(r"client-feedback", ClientFeedbackViewSet, basename="client-feedback")

# ----------------------------------------------
# URL Patterns
# ----------------------------------------------
urlpatterns = [
    path("", include(router.urls)),
]
