# ===============================================
# notifications/urls.py
# ===============================================

from django.urls import path
from .views import NotificationListView, MarkNotificationReadView

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="notifications-list"),
    path("<int:pk>/mark-read/", MarkNotificationReadView.as_view(), name="notifications-mark-read"),
]
