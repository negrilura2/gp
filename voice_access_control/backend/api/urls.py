from django.urls import path
from .views import (
    RegisterView, LoginView,
    EnrollView, VerifyView,
    VerifyLogListView, EnrollLogListView,
    UserListView, UserDeleteView,
    StatsView, CurrentUserView,
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
    path('logs/', VerifyLogListView.as_view(), name='verify-logs'),
    path('enroll-logs/', EnrollLogListView.as_view(), name='enroll-logs'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDeleteView.as_view(), name='user-delete'),
    path('stats/', StatsView.as_view(), name='stats'),
]
