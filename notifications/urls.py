# ===============================================
# notifications/urls.py
# ===============================================
"""
URL configuration for the notifications app.

Provides RESTful endpoints for:
- Listing notifications with filters
- Retrieving, updating, deleting individual notifications
- Bulk operations (mark read, delete)
- Admin operations (create, cleanup, statistics)
- Unread count for UI badge
"""

from django.urls import path
from .views import (
    # List and Detail
    NotificationListView,
    NotificationDetailView,
    
    # Status Operations
    UnreadCountView,
    MarkNotificationReadView,
    MarkNotificationUnreadView,
    
    # Bulk Operations
    BulkMarkReadView,
    BulkDeleteView,
    NotificationDeleteView,
    
    # Admin Operations
    CleanupExpiredNotificationsView,
    NotificationCreateView,
    NotificationStatisticsView,
)

app_name = "notifications"

# ===========================================================
# ROUTE SUMMARY
# ===========================================================
"""
Notification Endpoints:
-------------------------------------------------------------
USER ENDPOINTS:
🔔 GET    /                              → List notifications (with filters)
🔔 GET    /<id>/                         → Get notification detail
🔔 PATCH  /<id>/                         → Update notification
🔔 DELETE /<id>/                         → Delete notification

📊 GET    /unread-count/                 → Get unread count (for badge)

✓ PATCH   /<id>/mark-read/              → Mark single as read
◯ PATCH   /<id>/mark-unread/            → Mark single as unread

📦 POST   /bulk-mark-read/               → Bulk mark as read
🗑️ POST   /bulk-delete/                  → Bulk delete

ADMIN ENDPOINTS:
👤 POST   /admin/create/                 → Create notification
🧹 POST   /admin/cleanup-expired/        → Cleanup expired notifications
📈 GET    /admin/statistics/             → Get notification statistics

-------------------------------------------------------------
Query Parameters (for list endpoint):
  - status: unread|read|all
  - priority: urgent|high|medium|low
  - category: performance|feedback|system|attendance|leave|announcement
  - auto_delete: true|false
  - expired: true|false
  - date_from: YYYY-MM-DD
  - date_to: YYYY-MM-DD
  - search: search term
  - ordering: field|-field
  - page: page number
  - page_size: items per page

-------------------------------------------------------------
All endpoints require authentication.
Admin endpoints require admin/staff permissions.
"""

# ===========================================================
# URL Patterns
# ===========================================================
urlpatterns = [
    # ========== USER ENDPOINTS ==========
    
    # List and Detail
    path(
        "",
        NotificationListView.as_view(),
        name="notification_list"
    ),
    path(
        "<int:pk>/",
        NotificationDetailView.as_view(),
        name="notification_detail"
    ),
    
    # Unread Count (for UI badge)
    path(
        "unread-count/",
        UnreadCountView.as_view(),
        name="unread_count"
    ),
    
    # Single Notification Actions
    path(
        "<int:pk>/mark-read/",
        MarkNotificationReadView.as_view(),
        name="mark_read"
    ),
    path(
        "<int:pk>/mark-unread/",
        MarkNotificationUnreadView.as_view(),
        name="mark_unread"
    ),
    
    # Bulk Operations
    path(
        "bulk-mark-read/",
        BulkMarkReadView.as_view(),
        name="bulk_mark_read"
    ),
    path(
        "bulk-delete/",
        BulkDeleteView.as_view(),
        name="bulk_delete"
    ),
    
    # ========== ADMIN ENDPOINTS ==========
    
    # Create Notification (Admin)
    path(
        "admin/create/",
        NotificationCreateView.as_view(),
        name="admin_create"
    ),
    
    # Cleanup Expired (Admin)
    path(
        "admin/cleanup-expired/",
        CleanupExpiredNotificationsView.as_view(),
        name="admin_cleanup_expired"
    ),
    
    # Statistics (Admin)
    path(
        "admin/statistics/",
        NotificationStatisticsView.as_view(),
        name="admin_statistics"
    ),
]

# ===========================================================
# URL REFERENCE EXAMPLES
# ===========================================================
"""
Usage in views (reverse lookup):
    from django.urls import reverse
    
    # User endpoints
    list_url = reverse('notifications:notification_list')
    detail_url = reverse('notifications:notification_detail', kwargs={'pk': 1})
    unread_url = reverse('notifications:unread_count')
    mark_read_url = reverse('notifications:mark_read', kwargs={'pk': 1})
    
    # Bulk operations
    bulk_read_url = reverse('notifications:bulk_mark_read')
    bulk_delete_url = reverse('notifications:bulk_delete')
    
    # Admin endpoints
    create_url = reverse('notifications:admin_create')
    cleanup_url = reverse('notifications:admin_cleanup_expired')
    stats_url = reverse('notifications:admin_statistics')

Usage in templates:
    {% url 'notifications:notification_list' %}
    {% url 'notifications:notification_detail' pk=notification.id %}
    {% url 'notifications:unread_count' %}
    {% url 'notifications:mark_read' pk=notification.id %}

API Usage Examples:

1. List notifications with filters:
   GET /api/notifications/?status=unread&priority=urgent&page=1

2. Get unread count:
   GET /api/notifications/unread-count/
   Response: {"unread_count": 5, "urgent_unread_count": 2}

3. Mark notification as read:
   PATCH /api/notifications/123/mark-read/
   Response: {"message": "...", "notification_id": 123, "auto_deleted": false}

4. Bulk mark as read:
   POST /api/notifications/bulk-mark-read/
   Body: {"notification_ids": [1, 2, 3]} or {} for all
   Response: {"marked_read": 3, "auto_deleted": 2, "total_processed": 5}

5. Bulk delete:
   POST /api/notifications/bulk-delete/
   Body: {"notification_ids": [1, 2, 3]}
   Response: {"deleted_count": 3}

6. Admin create notification:
   POST /api/notifications/admin/create/
   Body: {
       "employee_id": 1,
       "message": "Your report is ready",
       "category": "performance",
       "priority": "high",
       "link": "/reports/weekly/"
   }

7. Admin statistics:
   GET /api/notifications/admin/statistics/?date_from=2025-01-01&date_to=2025-12-31
   Response: {
       "total_notifications": 1000,
       "read_notifications": 850,
       "unread_notifications": 150,
       "priority_breakdown": {...},
       "category_breakdown": {...}
   }
"""