# performance/urls.py
from django.urls import path
from .views import (
    PerformanceListCreateView,
    PerformanceDetailView,
    PerformanceSummaryView
)

urlpatterns = [
    path('', PerformanceListCreateView.as_view(), name='performance-list-create'),
    path('<int:pk>/', PerformanceDetailView.as_view(), name='performance-detail'),
    path('summary/', PerformanceSummaryView.as_view(), name='performance-summary'),
]
