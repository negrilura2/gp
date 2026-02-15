from .views_auth import RegisterView, LoginView, CurrentUserView
from .views_voice import EnrollView, VerifyView, VoiceprintStatusView
from .views_logs import VerifyLogListView, VerifyLogBulkDeleteView, MyVerifyLogListView, EnrollLogListView
from .views_users import UserListView, UserDetailView, UserResetPasswordView, UserVoiceprintResetView
from .views_admin import (
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
)
from .views_stats import StatsView, DashboardView
from .views_roc import RocView, RocEvaluateView, RocEvaluateStatusView, ThresholdConfigView
from .view_utils import IsAdminUser
