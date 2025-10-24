# ===============================================
# feedback/urls.py (Final Verified Version)
# ===============================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GeneralFeedbackViewSet,
    ManagerFeedbackViewSet,
    ClientFeedbackViewSet,
    MyFeedbackView,   # ✅ Employee's all feedback view
)

app_name = "feedback"

"""
Routes for Feedback Module:
---------------------------
Includes:
- General Feedback APIs (Admin/HR)
- Manager Feedback APIs
- Client Feedback APIs
- My Feedback (Employee self-dashboard)
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
    path("my-feedback/", MyFeedbackView.as_view(), name="my-feedback"),  # ✅ Employee’s all feedback
]
