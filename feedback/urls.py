# ===============================================
# feedback/urls.py 
# ===============================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GeneralFeedbackViewSet,
    ManagerFeedbackViewSet,
    ClientFeedbackViewSet,
    MyFeedbackView,
)

app_name = "feedback"

"""
Feedback Module API Routes
--------------------------
🔹 /api/feedback/general-feedback/   → Admin/HR feedback CRUD
🔹 /api/feedback/manager-feedback/   → Manager feedback CRUD
🔹 /api/feedback/client-feedback/    → Client feedback CRUD
🔹 /api/feedback/my-feedback/        → Employee self feedback dashboard
"""

# -----------------------------------------------------------
# DRF Router Configuration
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r"general-feedback", GeneralFeedbackViewSet, basename="general-feedback")
router.register(r"manager-feedback", ManagerFeedbackViewSet, basename="manager-feedback")
router.register(r"client-feedback", ClientFeedbackViewSet, basename="client-feedback")

# -----------------------------------------------------------
# URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    path("", include(router.urls)),
    path("my-feedback/", MyFeedbackView.as_view(), name="my-feedback"),
]
