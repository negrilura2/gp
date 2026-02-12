"""
API Views — 声纹门禁系统

端点：
- POST /api/register/  — 用户注册
- POST /api/login/     — 用户登录（获取 Token）
- POST /api/enroll/    — 声纹注册（需认证）
- POST /api/verify/    — 声纹验证（可匿名）
- GET  /api/logs/      — 验证日志（管理员）
- GET  /api/stats/     — 统计数据（管理员，ECharts 用）
- GET  /api/users/     — 用户列表（管理员）
- DELETE /api/users/<id>/  — 删除用户（管理员）
"""
import os
import sys
import time
import logging
import librosa
import soundfile as sf
import numpy as np

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics
from rest_framework.authtoken.models import Token

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.http import FileResponse
from django.db.models import Count, Avg, Q
from django.db.models.functions import TruncDate

from .models import VoiceTemplate, VerifyLog, EnrollLog
from .serializers import (
    UserRegisterSerializer, UserSerializer,
    VoiceTemplateSerializer, VerifyLogSerializer, EnrollLogSerializer,
)

logger = logging.getLogger('api')

# ---- 项目根路径 & 模型导入 ----
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from model.enroll import enroll as model_enroll
from model.verify_demo import verify as model_verify
from .model_loader import get_model

# ---- 文件上传限制 ----
MAX_UPLOAD_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a'}


def get_client_ip(request):
    """从请求中获取客户端 IP"""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')


def validate_audio_file(f):
    """校验上传的音频文件"""
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的音频格式: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}")
    if f.size > MAX_UPLOAD_SIZE:
        raise ValueError(f"文件过大: {f.size / 1024 / 1024:.1f}MB，限制: {MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB")
    if f.size == 0:
        raise ValueError("文件为空")


def preprocess_audio(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == '.wav':
            y, sr = sf.read(path)
        else:
            y, sr = librosa.load(path, sr=None, mono=True)
    except Exception:
        y, sr = librosa.load(path, sr=None, mono=True)
    if y.ndim > 1:
        y = y.mean(axis=1)
    if len(y) == 0:
        raise ValueError("录音为空")
    if sr != 16000:
        y = librosa.resample(y, orig_sr=sr, target_sr=16000)
        sr = 16000
    out_path = path
    if ext != '.wav':
        out_path = os.path.splitext(path)[0] + '.wav'
    sf.write(out_path, y, sr)
    if out_path != path:
        os.remove(path)
    return out_path


# =========================================================
#  用户注册 / 登录
# =========================================================

class RegisterView(APIView):
    """用户注册 — 返回 Token"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        logger.info(f"用户注册: {user.username}")
        return Response({
            "user_id": user.id,
            "username": user.username,
            "token": token.key,
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """用户登录 — 返回 Token"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return Response({"error": "用户名和密码不能为空"}, status=400)

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({"error": "用户名或密码错误"}, status=401)

        token, _ = Token.objects.get_or_create(user=user)
        logger.info(f"用户登录: {username}")
        return Response({
            "user_id": user.id,
            "username": user.username,
            "is_staff": user.is_staff,
            "token": token.key,
        })


# =========================================================
#  声纹注册（需认证）
# =========================================================

class EnrollView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        form-data:
        - user_id (可选，默认当前用户名)
        - files: wav 文件列表
        """
        user_id = request.data.get('user_id', request.user.username)
        client_ip = get_client_ip(request)
        files = request.FILES.getlist('files')

        if not files:
            return Response({"error": "请至少上传一个音频文件"}, status=400)

        # 校验所有文件
        try:
            for f in files:
                validate_audio_file(f)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        if user_id != request.user.username and not request.user.is_staff:
            return Response({"error": "仅管理员可为其他用户注册声纹"}, status=403)

        target_user, _ = User.objects.get_or_create(username=user_id)

        # 保存文件到磁盘
        saved_paths = []
        user_dir = os.path.join(ROOT, 'data', 'enroll', user_id)
        os.makedirs(user_dir, exist_ok=True)

        for f in files:
            fname = f"{int(time.time() * 1000)}_{f.name}"
            path = os.path.join(user_dir, fname)
            with open(path, 'wb') as out:
                for chunk in f.chunks():
                    out.write(chunk)
            try:
                path = preprocess_audio(path)
            except Exception as e:
                return Response({"error": str(e)}, status=400)
            saved_paths.append(path)

        # 调用模型进行注册
        try:
            model_enroll(user_id, saved_paths)

            # 更新 VoiceTemplate 记录
            vt, created = VoiceTemplate.objects.update_or_create(
                user=target_user,
                defaults={
                    'template_path': os.path.join(ROOT, 'data', 'voiceprints', 'user_templates.npy'),
                    'embedding_count': len(saved_paths),
                }
            )

            # 记录日志
            EnrollLog.objects.create(
                user=target_user,
                username=target_user.username,
                wav_count=len(saved_paths),
                client_ip=client_ip,
                success=True,
            )

            logger.info(f"声纹注册成功: {user_id}, {len(saved_paths)} 条音频")
        except Exception as e:
            EnrollLog.objects.create(
                user=target_user,
                username=target_user.username,
                wav_count=len(saved_paths),
                client_ip=client_ip,
                success=False,
                error_msg=str(e),
            )
            logger.error(f"声纹注册失败: {user_id}, {e}")
            return Response({"error": str(e)}, status=500)

        return Response({
            "status": "enrolled",
            "user": user_id,
            "wav_count": len(saved_paths),
        })


# =========================================================
#  声纹验证（可匿名）
# =========================================================

class VerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        form-data:
        - file: wav 文件
        - threshold (可选，默认 0.75)
        """
        thr = float(request.data.get('threshold', 0.75))
        f = request.FILES.get('file')
        client_ip = get_client_ip(request)

        if not f:
            return Response({"error": "请上传一个音频文件"}, status=400)

        try:
            validate_audio_file(f)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        # 保存上传文件
        upload_dir = os.path.join(ROOT, 'data', 'verify_uploads')
        os.makedirs(upload_dir, exist_ok=True)
        fname = f"{int(time.time() * 1000)}_{f.name}"
        path = os.path.join(upload_dir, fname)
        with open(path, 'wb') as out:
            for chunk in f.chunks():
                out.write(chunk)
        try:
            path = preprocess_audio(path)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

        # 使用模型单例进行验证
        try:
            model, device = get_model()
            best_spk, best_score, result = model_verify(
                path,
                threshold=thr,
                model=model,
                device=device,
            )
        except FileNotFoundError as e:
            logger.warning(f"验证失败 — 模板不存在: {e}")
            return Response({"error": f"尚未注册任何声纹: {e}"}, status=404)
        except Exception as e:
            logger.error(f"验证异常: {e}")
            return Response({"error": str(e)}, status=500)

        # 记录日志
        VerifyLog.objects.create(
            request_user=request.user if request.user.is_authenticated else None,
            wav_path=path,
            predicted_user=str(best_spk),
            score=float(best_score),
            result=result,
            threshold=thr,
            client_ip=client_ip,
        )

        logger.info(f"声纹验证: {best_spk} score={best_score:.4f} => {result}")
        return Response({
            "predicted_user": str(best_spk),
            "score": float(best_score),
            "result": result,
            "threshold": thr,
        })


# =========================================================
#  管理员端点
# =========================================================

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class VerifyLogListView(generics.ListAPIView):
    """管理员查看验证日志列表（分页）"""
    serializer_class = VerifyLogSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = VerifyLog.objects.all()
        # 支持筛选
        result = self.request.query_params.get('result')
        if result:
            qs = qs.filter(result=result.upper())
        user = self.request.query_params.get('user')
        if user:
            qs = qs.filter(predicted_user__icontains=user)
        return qs


class MyVerifyLogListView(generics.ListAPIView):
    """用户查看自己的验证日志"""
    serializer_class = VerifyLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return VerifyLog.objects.filter(request_user=self.request.user)


class EnrollLogListView(generics.ListAPIView):
    """管理员查看注册日志列表"""
    serializer_class = EnrollLogSerializer
    permission_classes = [IsAdminUser]
    queryset = EnrollLog.objects.all()


class UserListView(generics.ListAPIView):
    """管理员查看用户列表"""
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    queryset = User.objects.all().order_by('-date_joined')


class UserDeleteView(generics.DestroyAPIView):
    """管理员删除用户"""
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    queryset = User.objects.all()


class VoiceTemplateListView(generics.ListAPIView):
    serializer_class = VoiceTemplateSerializer
    permission_classes = [IsAdminUser]
    queryset = VoiceTemplate.objects.select_related('user').all()


class VoiceTemplateDeleteView(generics.DestroyAPIView):
    serializer_class = VoiceTemplateSerializer
    permission_classes = [IsAdminUser]
    queryset = VoiceTemplate.objects.select_related('user').all()

    def perform_destroy(self, instance):
        template_path = instance.template_path or os.path.join(ROOT, 'data', 'voiceprints', 'user_templates.npy')
        if os.path.exists(template_path):
            try:
                templates = np.load(template_path, allow_pickle=True).item()
                username = instance.user.username
                if username in templates:
                    templates.pop(username, None)
                    np.save(template_path, templates)
            except Exception as e:
                logger.error(f"删除模板文件失败: {e}")
        instance.delete()


class StatsView(APIView):
    """统计数据 — 供 ECharts 前端使用"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        # 按天统计验证次数
        daily = (
            VerifyLog.objects
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(
                total=Count('id'),
                avg_score=Avg('score'),
                accept=Count('id', filter=Q(result='ACCEPT')),
                reject=Count('id', filter=Q(result='REJECT')),
            )
            .order_by('date')
        )
        daily_data = []
        for d in daily:
            total = d['total'] or 0
            accept = d['accept'] or 0
            reject = d['reject'] or 0
            rate = round(accept / total, 4) if total else 0
            daily_data.append({
                "date": str(d['date']),
                "total": total,
                "avg_score": round(d['avg_score'], 4) if d['avg_score'] else 0,
                "accept": accept,
                "reject": reject,
                "success_rate": rate,
            })

        # 结果分布
        accept_count = VerifyLog.objects.filter(result='ACCEPT').count()
        reject_count = VerifyLog.objects.filter(result='REJECT').count()

        # 用户数
        total_users = User.objects.count()
        enrolled_users = VoiceTemplate.objects.values('user').distinct().count()

        return Response({
            "daily": daily_data,
            "result_distribution": {
                "ACCEPT": accept_count,
                "REJECT": reject_count,
            },
            "users": {
                "total": total_users,
                "enrolled": enrolled_users,
            },
        })


class RocImageView(APIView):
    """获取 ROC 图像"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        roc_path = os.path.join(ROOT, 'reports', 'roc.png')
        if not os.path.exists(roc_path):
            return Response({"error": "ROC 图不存在"}, status=404)
        return FileResponse(open(roc_path, 'rb'), content_type='image/png')


class CurrentUserView(APIView):
    """获取当前登录用户信息"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        has_voiceprint = VoiceTemplate.objects.filter(user=user).exists()
        return Response({
            "user_id": user.id,
            "username": user.username,
            "is_staff": user.is_staff,
            "has_voiceprint": has_voiceprint,
            "date_joined": user.date_joined.isoformat(),
        })
