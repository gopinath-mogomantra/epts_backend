# ===============================================
# notifications/urls.py (Final Verified Version)
# ===============================================

from django.urls import path
from .views import NotificationListView, MarkNotificationReadView

app_name = "notifications"

"""
Routes for Notifications Module:
--------------------------------
- List all notifications (unread/read/all)
- Mark a specific notification as read (auto-delete if required)
"""

urlpatterns = [
    # 🔹 Fetch notifications for logged-in user
    path("", NotificationListView.as_view(), name="notifications-list"),

    # 🔹 Mark a specific notification as read (PATCH)
    path("<int:pk>/mark-read/", MarkNotificationReadView.as_view(), name="notifications-mark-read"),
]
