import os
import logging
from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics

from .models import AdminSecret, AdminAccessLog
from .serializers import (
    AdminSecretSetSerializer,
    AdminSecretVerifySerializer,
    AdminListUserSerializer,
    AdminAccessLogSerializer,
    AdminStaffCreateSerializer,
    AdminStaffUpdateSerializer,
)
from .model_loader import get_model, get_model_path, set_model_path
from .view_utils import get_client_ip, IsAdminUser

logger = logging.getLogger("api")


def with_last_admin_login(qs):
    last_login_subquery = (
        AdminAccessLog.objects.filter(
            user=OuterRef("pk"),
            action="ADMIN_LOGIN",
            success=True,
        )
        .order_by("-created_at")
        .values("created_at")[:1]
    )
    return qs.annotate(
        last_admin_login=Subquery(last_login_subquery, output_field=models.DateTimeField())
    )


class AdminSecretStatusView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        secret = AdminSecret.objects.first()
        return Response(
            {
                "configured": bool(secret),
                "updated_at": secret.updated_at.isoformat() if secret else None,
            }
        )


class AdminSecretSetView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        if not request.user.is_superuser:
            return Response({"error": "仅允许超级管理员设置高层密码"}, status=status.HTTP_403_FORBIDDEN)
        serializer = AdminSecretSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        current_password = serializer.validated_data["current_password"]
        secret_password = serializer.validated_data["secret_password"]
        if not request.user.check_password(current_password):
            AdminAccessLog.objects.create(
                action="ADMIN_SECRET_SET",
                user=request.user,
                success=False,
                client_ip=get_client_ip(request),
            )
            return Response({"error": "管理员密码错误"}, status=status.HTTP_403_FORBIDDEN)
        secret = AdminSecret.objects.first()
        if secret:
            secret.password_hash = make_password(secret_password)
            secret.updated_by = request.user
            secret.save(update_fields=["password_hash", "updated_by", "updated_at"])
        else:
            secret = AdminSecret.objects.create(
                password_hash=make_password(secret_password),
                updated_by=request.user,
            )
        AdminSecret.objects.exclude(id=secret.id).delete()
        AdminAccessLog.objects.create(
            action="ADMIN_SECRET_SET",
            user=request.user,
            success=True,
            client_ip=get_client_ip(request),
        )
        return Response(
            {
                "configured": True,
                "updated_at": secret.updated_at.isoformat(),
            }
        )


class AdminListView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = AdminSecretVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        secret_password = serializer.validated_data["secret_password"]
        secret = AdminSecret.objects.first()
        if not secret:
            AdminAccessLog.objects.create(
                action="ADMIN_LIST_ACCESS",
                user=request.user,
                success=False,
                client_ip=get_client_ip(request),
            )
            return Response({"error": "未设置高层密码"}, status=status.HTTP_400_BAD_REQUEST)
        if not check_password(secret_password, secret.password_hash):
            AdminAccessLog.objects.create(
                action="ADMIN_LIST_ACCESS",
                user=request.user,
                success=False,
                client_ip=get_client_ip(request),
            )
            return Response({"error": "高层密码错误"}, status=status.HTTP_403_FORBIDDEN)
        AdminAccessLog.objects.create(
            action="ADMIN_LIST_ACCESS",
            user=request.user,
            success=True,
            client_ip=get_client_ip(request),
        )
        qs = with_last_admin_login(User.objects.filter(is_staff=True)).order_by(
            "-last_admin_login",
            "username",
        )
        data = AdminListUserSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data})


class AdminStaffListView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all().order_by("-date_joined")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminStaffCreateSerializer
        return AdminListUserSerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(is_staff=True)
        keyword = self.request.query_params.get("q", "").strip()
        if keyword:
            qs = qs.filter(
                models.Q(username__icontains=keyword)
                | models.Q(email__icontains=keyword)
                | models.Q(profile__full_name__icontains=keyword)
                | models.Q(profile__phone__icontains=keyword)
                | models.Q(profile__department__icontains=keyword)
            )
        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            qs = qs.filter(is_active=is_active == "true")
        return with_last_admin_login(qs).order_by("-last_admin_login", "username")


class AdminStaffDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.filter(is_staff=True)

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return AdminStaffUpdateSerializer
        return AdminListUserSerializer

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)


class AdminStaffBulkStatusView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        ids = request.data.get("ids") or []
        is_active = request.data.get("is_active")
        if not isinstance(ids, list) or not ids:
            return Response({"error": "缺少管理员ID"}, status=status.HTTP_400_BAD_REQUEST)
        if is_active not in (True, False):
            return Response({"error": "缺少状态参数"}, status=status.HTTP_400_BAD_REQUEST)
        qs = User.objects.filter(is_staff=True, id__in=ids)
        updated = qs.update(is_active=is_active)
        return Response({"updated": updated})


class AdminStaffBulkResetPasswordView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        ids = request.data.get("ids") or []
        password = request.data.get("password")
        if not isinstance(ids, list) or not ids:
            return Response({"error": "缺少管理员ID"}, status=status.HTTP_400_BAD_REQUEST)
        if not password:
            return Response({"error": "缺少新密码"}, status=status.HTTP_400_BAD_REQUEST)
        qs = User.objects.filter(is_staff=True, id__in=ids)
        updated = 0
        for user in qs:
            user.set_password(password)
            user.save(update_fields=["password"])
            updated += 1
        return Response({"updated": updated})


class AdminAccessLogListView(generics.ListAPIView):
    serializer_class = AdminAccessLogSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return AdminAccessLog.objects.filter(action="ADMIN_LIST_ACCESS")


class ModelListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        models_dir = os.fspath(settings.MODELS_DIR)
        items = []
        if os.path.isdir(models_dir):
            for name in sorted(os.listdir(models_dir)):
                if not name.endswith(".pth"):
                    continue
                path = os.path.join(models_dir, name)
                try:
                    stat = os.stat(path)
                    items.append(
                        {
                            "name": name,
                            "path": path,
                            "size": stat.st_size,
                            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        }
                    )
                except OSError:
                    continue
        current_path = get_model_path()
        current_name = os.path.basename(current_path) if current_path else ""
        return Response(
            {
                "current": current_name,
                "models": items,
            }
        )


class ModelSwitchView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        name = request.data.get("name")
        if not name:
            return Response({"error": "缺少模型名称"}, status=status.HTTP_400_BAD_REQUEST)
        models_dir = os.fspath(settings.MODELS_DIR)
        path = os.path.join(models_dir, name)
        if not os.path.isfile(path):
            return Response({"error": "模型不存在"}, status=status.HTTP_404_NOT_FOUND)
        set_model_path(path)
        try:
            get_model(path)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(
            {
                "current": os.path.basename(path),
            }
        )
