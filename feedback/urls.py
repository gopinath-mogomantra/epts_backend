# ===============================================
# feedback/urls.py 
# ===============================================
"""
Enhanced Feedback Module API Routes with Statistics
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GeneralFeedbackViewSet,
    ManagerFeedbackViewSet,
    ClientFeedbackViewSet,
    MyFeedbackView,
    FeedbackStatisticsView,
)

app_name = "feedback"

# Router Configuration
router = DefaultRouter()
router.register(r"general", GeneralFeedbackViewSet, basename="general-feedback")
router.register(r"manager", ManagerFeedbackViewSet, basename="manager-feedback")
router.register(r"client", ClientFeedbackViewSet, basename="client-feedback")

# URL Patterns
urlpatterns = [
    # Router URLs
    path("", include(router.urls)),
    
    # Custom Endpoints
    path("my-feedback/", MyFeedbackView.as_view(), name="my-feedback"),
    path("statistics/", FeedbackStatisticsView.as_view(), name="statistics"),
]

"""
Available Endpoints:
--------------------
📊 GENERAL FEEDBACK:
  GET     /api/feedback/general/                    → List
  POST    /api/feedback/general/                    → Create
  GET     /api/feedback/general/{id}/               → Detail
  PATCH   /api/feedback/general/{id}/               → Update
  DELETE  /api/feedback/general/{id}/               → Delete
  POST    /api/feedback/general/{id}/acknowledge/   → Acknowledge
  POST    /api/feedback/general/{id}/complete-action/ → Complete action
  POST    /api/feedback/general/{id}/archive/       → Archive

👔 MANAGER FEEDBACK:
  GET     /api/feedback/manager/                    → List
  POST    /api/feedback/manager/                    → Create
  GET     /api/feedback/manager/{id}/               → Detail
  PATCH   /api/feedback/manager/{id}/               → Update
  DELETE  /api/feedback/manager/{id}/               → Delete
  POST    /api/feedback/manager/{id}/acknowledge/   → Acknowledge
  POST    /api/feedback/manager/{id}/complete-action/ → Complete action
  POST    /api/feedback/manager/{id}/archive/       → Archive

🤝 CLIENT FEEDBACK:
  GET     /api/feedback/client/                     → List
  POST    /api/feedback/client/                     → Create
  GET     /api/feedback/client/{id}/                → Detail
  PATCH   /api/feedback/client/{id}/                → Update
  DELETE  /api/feedback/client/{id}/                → Delete
  POST    /api/feedback/client/{id}/acknowledge/    → Acknowledge
  POST    /api/feedback/client/{id}/complete-action/ → Complete action
  POST    /api/feedback/client/{id}/archive/        → Archive

👤 EMPLOYEE:
  GET     /api/feedback/my-feedback/                → Employee dashboard

📈 STATISTICS:
  GET     /api/feedback/statistics/                 → Admin statistics

Query Parameters (List endpoints):
  - priority: urgent|high|normal|low
  - status: pending|reviewed|acknowledged|actioned|archived
  - sentiment: positive|neutral|negative|mixed
  - acknowledged: true|false
  - requires_action: true
  - min_rating: 1-10
  - max_rating: 1-10
  - date_from: YYYY-MM-DD
  - date_to: YYYY-MM-DD
  - search: search term
"""