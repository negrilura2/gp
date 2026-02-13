from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    EnrollView,
    VerifyView,
    VerifyLogListView,
    VerifyLogBulkDeleteView,
    MyVerifyLogListView,
    EnrollLogListView,
    UserListView,
    UserDeleteView,
    StatsView,
    DashboardView,
    CurrentUserView,
    VoiceprintStatusView,
    RocView,
    ThresholdConfigView,
)

urlpatterns = [
    # 用户
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', CurrentUserView.as_view(), name='current-user'),

    # 核心功能
    path('enroll/', EnrollView.as_view(), name='enroll'),
    path('verify/', VerifyView.as_view(), name='verify'),

    # 管理员
    path('my-logs/', MyVerifyLogListView.as_view(), name='my-logs'),
    path('logs/', VerifyLogListView.as_view(), name='verify-logs'),
    path('logs/bulk-delete/', VerifyLogBulkDeleteView.as_view(), name='verify-logs-bulk-delete'),
    path('enroll-logs/', EnrollLogListView.as_view(), name='enroll-logs'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDeleteView.as_view(), name='user-delete'),
    path('stats/', StatsView.as_view(), name='stats'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('threshold/', ThresholdConfigView.as_view(), name='threshold-config'),
    path('voiceprint-status/', VoiceprintStatusView.as_view(), name='voiceprint-status'),
    path('roc/', RocView.as_view(), name='roc'),
]
