# ===============================================
# notifications/urls.py 
# ===============================================

from django.urls import path
from .views import (
    NotificationListView,
    UnreadCountView,
    MarkNotificationReadView,
    MarkNotificationUnreadView,
    MarkAllNotificationsReadView,
    NotificationDeleteView,
)

app_name = "notifications"

"""
Routes for Notifications Module:
--------------------------------
🔹 Fetch, mark, and manage notifications for employees.
🔹 Used for frontend bell icon, dropdown, and dashboard alerts.

Available Endpoints:
--------------------------------
1️⃣ GET   /api/notifications/                     → List user notifications (filter by read/unread)
2️⃣ GET   /api/notifications/unread-count/        → Get unread count for header badge
3️⃣ PATCH /api/notifications/<id>/mark-read/      → Mark a specific notification as read
4️⃣ PATCH /api/notifications/<id>/mark-unread/    → Revert notification to unread (if persistent)
5️⃣ PATCH /api/notifications/mark-all-read/       → Mark all notifications as read
6️⃣ DELETE /api/notifications/<id>/delete/        → Delete a specific notification (owner/admin)
"""

urlpatterns = [
    # ----------------------------------------------------
    # List all notifications (Unread/Read/All)
    # ----------------------------------------------------
    path("", NotificationListView.as_view(), name="notifications-list"),

    # ----------------------------------------------------
    # Get unread count (for bell icon)
    # ----------------------------------------------------
    path("unread-count/", UnreadCountView.as_view(), name="notifications-unread-count"),

    # ----------------------------------------------------
    # Mark single notification as read
    # ----------------------------------------------------
    path("<int:pk>/mark-read/", MarkNotificationReadView.as_view(), name="notifications-mark-read"),

    # ----------------------------------------------------
    # Mark single notification as unread (revert)
    # ----------------------------------------------------
    path("<int:pk>/mark-unread/", MarkNotificationUnreadView.as_view(), name="notifications-mark-unread"),

    # ----------------------------------------------------
    # Mark all notifications as read
    # ----------------------------------------------------
    path("mark-all-read/", MarkAllNotificationsReadView.as_view(), name="notifications-mark-all-read"),

    # ----------------------------------------------------
    # 6Delete a single notification
    # ----------------------------------------------------
    path("<int:pk>/delete/", NotificationDeleteView.as_view(), name="notifications-delete"),
]
