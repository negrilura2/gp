from django.urls import path
from .views.auth import RegisterView, LoginView, CurrentUserView
from .views.voice import EnrollView, VerifyView, VoiceprintStatusView
from .views.logs import VerifyLogListView, VerifyLogBulkDeleteView, MyVerifyLogListView, EnrollLogListView
from .views.users import UserListView, UserDetailView, UserResetPasswordView, UserVoiceprintResetView, MyVoiceprintView
from .views.admin import (
    AdminSecretStatusView,
    AdminSecretSetView,
    AdminListView,
    AdminStaffListView,
    AdminStaffDetailView,
    AdminStaffBulkStatusView,
    AdminStaffBulkResetPasswordView,
    AdminAccessLogListView,
    ModelListView,
    ModelSwitchView,
    MaintenanceVerifyLogCleanView,
    MaintenanceModelCheckView,
    MaintenanceCacheCleanView,
)
from .views.stats import StatsView, DashboardView
from .views.roc import RocView, RocEvaluateView, RocEvaluateStatusView, ThresholdConfigView
from .views.analysis import EmbeddingImageView

urlpatterns = [
    # 用户
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/voiceprint/', MyVoiceprintView.as_view(), name='my-voiceprint'),

    # 核心功能
    path('enroll/', EnrollView.as_view(), name='enroll'),
    path('verify/', VerifyView.as_view(), name='verify'),

    # 管理员
    path('my-logs/', MyVerifyLogListView.as_view(), name='my-logs'),
    path('logs/', VerifyLogListView.as_view(), name='verify-logs'),
    path('logs/bulk-delete/', VerifyLogBulkDeleteView.as_view(), name='verify-logs-bulk-delete'),
    path('enroll-logs/', EnrollLogListView.as_view(), name='enroll-logs'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),
    path('users/<int:pk>/reset-password/', UserResetPasswordView.as_view(), name='user-reset-password'),
    path('users/<int:pk>/voiceprint/', UserVoiceprintResetView.as_view(), name='user-voiceprint-reset'),
    path('admin-secret/', AdminSecretSetView.as_view(), name='admin-secret-set'),
    path('admin-secret/status/', AdminSecretStatusView.as_view(), name='admin-secret-status'),
    path('admin-list/', AdminListView.as_view(), name='admin-list'),
    path('admins/', AdminStaffListView.as_view(), name='admin-staff-list'),
    path('admins/<int:pk>/', AdminStaffDetailView.as_view(), name='admin-staff-detail'),
    path('admins/bulk-status/', AdminStaffBulkStatusView.as_view(), name='admin-staff-bulk-status'),
    path('admins/bulk-reset-password/', AdminStaffBulkResetPasswordView.as_view(), name='admin-staff-bulk-reset-password'),
    path('admin-access-logs/', AdminAccessLogListView.as_view(), name='admin-access-logs'),
    path('models/', ModelListView.as_view(), name='model-list'),
    path('models/switch/', ModelSwitchView.as_view(), name='model-switch'),
    path('maintenance/logs-clean/', MaintenanceVerifyLogCleanView.as_view(), name='maintenance-logs-clean'),
    path('maintenance/models-check/', MaintenanceModelCheckView.as_view(), name='maintenance-models-check'),
    path('maintenance/cache-clean/', MaintenanceCacheCleanView.as_view(), name='maintenance-cache-clean'),
    path('stats/', StatsView.as_view(), name='stats'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('threshold/', ThresholdConfigView.as_view(), name='threshold-config'),
    path('voiceprint-status/', VoiceprintStatusView.as_view(), name='voiceprint-status'),
    path('roc/', RocView.as_view(), name='roc'),
    path('roc/evaluate/', RocEvaluateView.as_view(), name='roc-evaluate'),
    path('roc/evaluate/status/', RocEvaluateStatusView.as_view(), name='roc-evaluate-status'),
    path('analysis/embedding/image/', EmbeddingImageView.as_view(), name='embedding-image'),
]
