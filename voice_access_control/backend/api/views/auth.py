import logging

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token

from ..models import VoiceTemplate, AdminAccessLog
from ..serializers import UserRegisterSerializer
from ..view_utils import get_client_ip

logger = logging.getLogger("api")


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        logger.info(f"用户注册: {user.username}")
        return Response(
            {
                "user_id": user.id,
                "username": user.username,
                "token": token.key,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response({"error": "用户名和密码不能为空"}, status=400)

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"error": "用户名或密码错误"}, status=401)

        token, _ = Token.objects.get_or_create(user=user)
        logger.info(f"用户登录: {username}")
        if user.is_staff:
            AdminAccessLog.objects.create(
                action="ADMIN_LOGIN",
                user=user,
                success=True,
                client_ip=get_client_ip(request),
            )
        return Response(
            {
                "user_id": user.id,
                "username": user.username,
                "is_staff": user.is_staff,
                "token": token.key,
            }
        )


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        has_voiceprint = VoiceTemplate.objects.filter(user=user).exists()
        return Response(
            {
                "user_id": user.id,
                "username": user.username,
                "is_staff": user.is_staff,
                "has_voiceprint": has_voiceprint,
                "date_joined": timezone.localtime(user.date_joined).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
