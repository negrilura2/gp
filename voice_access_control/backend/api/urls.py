from django.urls import path
from .views import (
    RegisterView, LoginView,
    EnrollView, VerifyView,
    VerifyLogListView, EnrollLogListView, MyVerifyLogListView,
    UserListView, UserDeleteView,
    VoiceTemplateListView, VoiceTemplateDeleteView,
    StatsView, CurrentUserView, RocImageView,
)

urlpatterns = [
    # 用户
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('me/', CurrentUserView.as_view(), name='current-user'),

    # 核心功能
    path('enroll/', EnrollView.as_view(), name='enroll'),
    path('verify/', VerifyView.as_view(), name='verify'),
    path('my-logs/', MyVerifyLogListView.as_view(), name='my-verify-logs'),

    # 管理员
    path('logs/', VerifyLogListView.as_view(), name='verify-logs'),
    path('enroll-logs/', EnrollLogListView.as_view(), name='enroll-logs'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDeleteView.as_view(), name='user-delete'),
    path('voice-templates/', VoiceTemplateListView.as_view(), name='voice-template-list'),
    path('voice-templates/<int:pk>/', VoiceTemplateDeleteView.as_view(), name='voice-template-delete'),
    path('stats/', StatsView.as_view(), name='stats'),
    path('roc/', RocImageView.as_view(), name='roc-image'),
]
