import os
import logging
import shutil

import numpy as np

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics

from .models import VoiceTemplate
from .serializers import (
    AdminUserCreateSerializer,
    AdminUserUpdateSerializer,
    AdminPasswordResetSerializer,
    UserSerializer,
)
from .view_utils import IsAdminUser

logger = logging.getLogger("api")


class UserListView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all().order_by("-date_joined")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(is_staff=False)
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

        has_voiceprint = self.request.query_params.get("has_voiceprint")
        if has_voiceprint in ("true", "false"):
            user_ids = VoiceTemplate.objects.values_list("user_id", flat=True).distinct()
            if has_voiceprint == "true":
                qs = qs.filter(id__in=user_ids)
            else:
                qs = qs.exclude(id__in=user_ids)
        return qs


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return AdminUserUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        username = instance.username
        result = remove_user_voiceprint(username)
        if result.get("error"):
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.perform_destroy(instance)
        return Response(result, status=status.HTTP_200_OK)


class UserResetPasswordView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        serializer = AdminPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data["password"]
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
        user.set_password(password)
        user.save(update_fields=["password"])
        return Response({"status": "ok", "user_id": user.id})


class UserVoiceprintResetView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        user = User.objects.filter(pk=pk).first()
        if not user:
            return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)
        result = remove_user_voiceprint(user.username)
        if result.get("error"):
            return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(result, status=status.HTTP_200_OK)


def remove_user_voiceprint(username):
    template_path = os.path.join(os.fspath(settings.VOICEPRINTS_DIR), "user_templates.npy")
    result = {
        "username": username,
        "template_cleared": False,
        "enroll_files_deleted": False,
        "template_path": template_path,
        "error": None,
    }
    try:
        if os.path.exists(template_path):
            templates = np.load(template_path, allow_pickle=True).item()
            if username in templates:
                del templates[username]
                np.save(template_path, templates)
                result["template_cleared"] = True
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"清理声纹模板失败: {username} {e}")
        return result

    try:
        VoiceTemplate.objects.filter(user__username=username).delete()
        enroll_dir = os.path.join(os.fspath(settings.ENROLL_DIR), username)
        if os.path.exists(enroll_dir):
            shutil.rmtree(enroll_dir)
            result["enroll_files_deleted"] = True
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"清理注册文件失败: {username} {e}")
    return result
