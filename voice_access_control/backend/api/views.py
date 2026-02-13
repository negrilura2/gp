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
import json
from datetime import datetime, timedelta
import soundfile as sf

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics
from rest_framework.authtoken.models import Token

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.conf import settings
from django.db import models
from django.db.models import Count, Avg, Max, Min
from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import VoiceTemplate, VerifyLog, EnrollLog
from .serializers import (
    UserRegisterSerializer, UserSerializer,
    VoiceTemplateSerializer, VerifyLogSerializer, EnrollLogSerializer,
    ThresholdConfigSerializer, get_effective_threshold,
)

logger = logging.getLogger('api')

# ---- 项目根路径 & 模型导入 ----
ROOT = os.fspath(settings.PROJECT_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from model.enroll import enroll as model_enroll
from model.verify_demo import verify as model_verify
from .model_loader import get_model

# ---- 文件上传限制 ----
MAX_UPLOAD_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_EXTENSIONS = {'.wav'}


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
    try:
        f.seek(0)
        data, _ = sf.read(f)
        f.seek(0)
    except Exception:
        raise ValueError("音频解析失败，请上传 WAV 文件")
    if data is None or len(data) == 0:
        raise ValueError("音频文件为空")


def count_files(root, exts=None):
    if not os.path.exists(root):
        return 0
    total = 0
    for _, _, files in os.walk(root):
        for name in files:
            if exts is None or os.path.splitext(name)[1].lower() in exts:
                total += 1
    return total


def get_latest_file_info(root, exts=None):
    if not os.path.exists(root):
        return {"name": None, "mtime": None}
    latest_path = None
    latest_mtime = -1
    for base, _, files in os.walk(root):
        for name in files:
            if exts is None or os.path.splitext(name)[1].lower() in exts:
                path = os.path.join(base, name)
                mtime = os.path.getmtime(path)
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_path = path
    if latest_path is None:
        return {"name": None, "mtime": None}
    return {
        "name": os.path.basename(latest_path),
        "mtime": datetime.fromtimestamp(latest_mtime).isoformat(),
    }


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
        user_id = request.data.get('user_id', '').strip()
        if not request.user.is_staff or not user_id:
            user_id = request.user.username
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

        # 保存文件到磁盘
        saved_paths = []
        user_dir = os.path.join(os.fspath(settings.ENROLL_DIR), user_id)
        os.makedirs(user_dir, exist_ok=True)

        for f in files:
            fname = f"{int(time.time() * 1000)}_{f.name}"
            path = os.path.join(user_dir, fname)
            with open(path, 'wb') as out:
                for chunk in f.chunks():
                    out.write(chunk)
            saved_paths.append(path)

        # 调用模型进行注册
        try:
            model_enroll(user_id, saved_paths)

            # 更新 VoiceTemplate 记录
            vt, created = VoiceTemplate.objects.update_or_create(
                user=request.user,
                defaults={
                    'template_path': os.path.join(os.fspath(settings.VOICEPRINTS_DIR), 'user_templates.npy'),
                    'embedding_count': len(saved_paths),
                }
            )

            # 记录日志
            EnrollLog.objects.create(
                user=request.user,
                username=user_id,
                wav_count=len(saved_paths),
                client_ip=client_ip,
                success=True,
            )

            logger.info(f"声纹注册成功: {user_id}, {len(saved_paths)} 条音频")
        except Exception as e:
            EnrollLog.objects.create(
                user=request.user,
                username=user_id,
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
        - threshold (可选，默认 settings.VOICE_VERIFY_THRESHOLD)
        """
        try:
            thr_raw = request.data.get('threshold', None)
            if thr_raw is None or thr_raw == "":
                thr = settings.VOICE_VERIFY_THRESHOLD
            else:
                thr = float(thr_raw)
        except (TypeError, ValueError):
            return Response({"error": "threshold 必须是数字"}, status=400)
        if not (0 < thr < 1):
            return Response({"error": "threshold 必须在 0~1 之间"}, status=400)
        f = request.FILES.get('file')
        client_ip = get_client_ip(request)

        if not f:
            return Response({"error": "请上传一个音频文件"}, status=400)

        try:
            validate_audio_file(f)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        # 保存上传文件
        upload_dir = os.fspath(settings.RECORDINGS_DIR)
        os.makedirs(upload_dir, exist_ok=True)
        fname = f"{int(time.time() * 1000)}_{f.name}"
        path = os.path.join(upload_dir, fname)
        with open(path, 'wb') as out:
            for chunk in f.chunks():
                out.write(chunk)

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
            VerifyLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                wav_path=path,
                predicted_user="UNKNOWN",
                score=0.0,
                result="ERROR",
                door_state="CLOSED",
                threshold=thr,
                client_ip=client_ip,
                error_msg=str(e),
            )
            return Response({"error": f"尚未注册任何声纹: {e}"}, status=404)
        except Exception as e:
            logger.error(f"验证异常: {e}")
            VerifyLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                wav_path=path,
                predicted_user="UNKNOWN",
                score=0.0,
                result="ERROR",
                door_state="CLOSED",
                threshold=thr,
                client_ip=client_ip,
                error_msg=str(e),
            )
            return Response({"error": str(e)}, status=500)

        door_state = "OPEN" if result == "ACCEPT" else "CLOSED"
        matched_user = User.objects.filter(username=str(best_spk)).first()
        user_info = None
        if matched_user and result == "ACCEPT":
            user_info = {
                "id": matched_user.id,
                "username": matched_user.username,
                "email": matched_user.email,
                "is_staff": matched_user.is_staff,
            }

        # 记录日志
        VerifyLog.objects.create(
            user=request.user if request.user.is_authenticated else None,
            wav_path=path,
            predicted_user=str(best_spk),
            score=float(best_score),
            result=result,
            door_state=door_state,
            threshold=thr,
            client_ip=client_ip,
            error_msg="",
        )

        logger.info(f"声纹验证: {best_spk} score={best_score:.4f} => {result}")
        return Response({
            "predicted_user": str(best_spk),
            "score": float(best_score),
            "result": result,
            "door_state": door_state,
            "user_info": user_info,
            "threshold": thr,
        })


class VoiceprintStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        total_templates = VoiceTemplate.objects.count()
        data = {
            "has_any_voiceprint": total_templates > 0,
            "total_templates": total_templates,
            "total_users": User.objects.count(),
        }
        if request.user and request.user.is_authenticated:
            data["has_my_voiceprint"] = VoiceTemplate.objects.filter(user=request.user).exists()
        return Response(data)


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
        # 按模型预测用户名筛选（predicted / user 参数，user 作为兼容别名）
        predicted = self.request.query_params.get('predicted')
        user_param = self.request.query_params.get('user')
        name = predicted or user_param
        if name:
            qs = qs.filter(predicted_user__icontains=name)

        # 按请求发起人用户名筛选（actor 参数）
        actor = self.request.query_params.get('actor')
        if actor:
            qs = qs.filter(user__username__icontains=actor)

        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)

        def _to_float(param):
            try:
                return float(param)
            except (TypeError, ValueError):
                return None

        min_score = _to_float(self.request.query_params.get('min_score'))
        max_score = _to_float(self.request.query_params.get('max_score'))
        if min_score is not None:
            qs = qs.filter(score__gte=min_score)
        if max_score is not None:
            qs = qs.filter(score__lte=max_score)

        min_thr = _to_float(self.request.query_params.get('min_threshold'))
        max_thr = _to_float(self.request.query_params.get('max_threshold'))
        if min_thr is not None:
            qs = qs.filter(threshold__gte=min_thr)
        if max_thr is not None:
            qs = qs.filter(threshold__lte=max_thr)
        return qs


class MyVerifyLogListView(generics.ListAPIView):
    serializer_class = VerifyLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = VerifyLog.objects.filter(
            models.Q(user=user) | models.Q(predicted_user=user.username)
        )
        return qs.order_by("-timestamp")[:100]


class VerifyLogBulkDeleteView(APIView):
    """管理员批量删除验证日志"""
    permission_classes = [IsAdminUser]

    def delete(self, request):
        ids = request.data.get('ids') or []
        if not isinstance(ids, list):
            return Response({"error": "ids 必须是列表"}, status=status.HTTP_400_BAD_REQUEST)
        ids = [int(i) for i in ids if str(i).isdigit()]
        if not ids:
            return Response({"deleted": 0})
        deleted, _ = VerifyLog.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted})


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


class StatsView(APIView):
    """统计数据 — 供 ECharts 前端使用"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        mode = request.query_params.get('mode', '').lower()

        # 按天统计验证次数
        daily = (
            VerifyLog.objects
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(
                total=Count('id'),
                avg_score=Avg('score'),
                accept_count=Count('id', filter=models.Q(result='ACCEPT')),
                reject_count=Count('id', filter=models.Q(result='REJECT')),
            )
            .order_by('date')
        )
        daily_data = [
            {
                "date": str(d['date']),
                "total": d['total'],
                "avg_score": round(d['avg_score'], 4) if d['avg_score'] else 0,
                "accept_rate": round(d['accept_count'] / d['total'], 4) if d['total'] else 0,
            }
            for d in daily
        ]

        # 结果分布
        accept_count = VerifyLog.objects.filter(result='ACCEPT').count()
        reject_count = VerifyLog.objects.filter(result='REJECT').count()
        total_count = accept_count + reject_count
        accept_rate = round(accept_count / total_count, 4) if total_count else 0

        # 时间窗口汇总
        now = timezone.now()
        last_7_qs = VerifyLog.objects.filter(timestamp__gte=now - timedelta(days=7))
        last_30_qs = VerifyLog.objects.filter(timestamp__gte=now - timedelta(days=30))

        def _window_summary(qs):
            total = qs.count()
            if total == 0:
                return {"total": 0, "accept_rate": 0}
            acc = qs.filter(result='ACCEPT').count()
            return {
                "total": total,
                "accept_rate": round(acc / total, 4),
            }

        window_summary = {
            "last_7_days": _window_summary(last_7_qs),
            "last_30_days": _window_summary(last_30_qs),
        }

        # 分数统计
        score_stats = {"max": 0, "min": 0, "avg": 0, "median": 0}
        all_qs = VerifyLog.objects.all()
        if all_qs.exists():
            agg = all_qs.aggregate(
                max_score=Max('score'),
                min_score=Min('score'),
                avg_score=Avg('score'),
            )
            scores = list(all_qs.order_by('score').values_list('score', flat=True))
            n = len(scores)
            if n > 0:
                if n % 2 == 1:
                    median = float(scores[n // 2])
                else:
                    median = float((scores[n // 2 - 1] + scores[n // 2]) / 2.0)
                score_stats = {
                    "max": float(agg["max_score"]) if agg["max_score"] is not None else 0,
                    "min": float(agg["min_score"]) if agg["min_score"] is not None else 0,
                    "avg": float(agg["avg_score"]) if agg["avg_score"] is not None else 0,
                    "median": median,
                }

        # 用户数
        total_users = User.objects.count()
        enrolled_users = VoiceTemplate.objects.values('user').distinct().count()

        if mode == "echarts":
            x_axis = [d["date"] for d in daily_data]
            return Response({
                "xAxis": x_axis,
                "series": {
                    "verify_total": [d["total"] for d in daily_data],
                    "accept_rate": [d["accept_rate"] for d in daily_data],
                },
                "pie": [
                    {"name": "ACCEPT", "value": accept_count},
                    {"name": "REJECT", "value": reject_count},
                ],
                "users": {
                    "total": total_users,
                    "enrolled": enrolled_users,
                },
                "window_summary": window_summary,
                "score_stats": score_stats,
            })

        return Response({
            "daily": daily_data,
            "result_distribution": {
                "ACCEPT": accept_count,
                "REJECT": reject_count,
                "ACCEPT_RATE": accept_rate,
            },
            "users": {
                "total": total_users,
                "enrolled": enrolled_users,
            },
            "window_summary": window_summary,
            "score_stats": score_stats,
        })


class DashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.count()
        admin_users = User.objects.filter(is_staff=True).count()
        enrolled_users = VoiceTemplate.objects.values('user').distinct().count()

        verify_total = VerifyLog.objects.count()
        verify_accept = VerifyLog.objects.filter(result='ACCEPT').count()
        verify_reject = VerifyLog.objects.filter(result='REJECT').count()
        verify_rate = round(verify_accept / verify_total, 4) if verify_total else 0

        enroll_total = EnrollLog.objects.count()
        enroll_success = EnrollLog.objects.filter(success=True).count()
        enroll_rate = round(enroll_success / enroll_total, 4) if enroll_total else 0

        verify_daily = (
            VerifyLog.objects
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(total=Count('id'))
            .order_by('date')
        )
        enroll_daily = (
            EnrollLog.objects
            .annotate(date=TruncDate('timestamp'))
            .values('date')
            .annotate(total=Count('id'))
            .order_by('date')
        )

        model_info = get_latest_file_info(os.fspath(settings.MODELS_DIR), {'.pth', '.pt', '.onnx'})

        return Response({
            "summary": {
                "users_total": total_users,
                "users_admin": admin_users,
                "users_enrolled": enrolled_users,
                "verify_total": verify_total,
                "verify_accept": verify_accept,
                "verify_reject": verify_reject,
                "verify_accept_rate": verify_rate,
                "enroll_total": enroll_total,
                "enroll_success": enroll_success,
                "enroll_success_rate": enroll_rate,
                "threshold_default": get_effective_threshold(),
            },
            "data_assets": {
                "raw_wav": count_files(os.fspath(settings.RAW_DIR), {'.wav'}),
                "processed_wav": count_files(os.fspath(settings.PROCESSED_DIR), {'.wav'}),
                "feature_files": count_files(os.fspath(settings.FEATURES_DIR), {'.npy'}),
                "voiceprints": count_files(os.fspath(settings.VOICEPRINTS_DIR), {'.npy'}),
                "recordings": count_files(os.fspath(settings.RECORDINGS_DIR), {'.wav', '.flac', '.mp3', '.ogg', '.m4a'}),
            },
            "trend": {
                "verify_daily": [{"date": str(d['date']), "total": d['total']} for d in verify_daily],
                "enroll_daily": [{"date": str(d['date']), "total": d['total']} for d in enroll_daily],
            },
            "model": {
                "count": count_files(os.fspath(settings.MODELS_DIR), {'.pth', '.pt', '.onnx'}),
                "latest_name": model_info["name"],
                "latest_mtime": model_info["mtime"],
            },
        })


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
            "date_joined": timezone.localtime(user.date_joined).strftime("%Y-%m-%d %H:%M:%S"),
        })


class RocView(APIView):
    """离线 ROC / EER 结果 — 供前端可视化"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        reports_dir = os.fspath(settings.REPORTS_DIR)
        eer_path = os.path.join(reports_dir, "eer_threshold.json")
        roc_points_path = os.path.join(reports_dir, "roc_points.json")

        if not os.path.exists(eer_path):
            return Response({"error": "eer_threshold.json not found, 请先运行阈值评估脚本"}, status=404)

        with open(eer_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        roc_data = None
        if os.path.exists(roc_points_path):
            with open(roc_points_path, "r", encoding="utf-8") as f:
                roc_data = json.load(f)

        thr_eer = metrics.get("threshold")
        thr_default = getattr(settings, "VOICE_VERIFY_THRESHOLD", None)
        threshold_diff = None
        if thr_eer is not None and thr_default is not None:
            threshold_diff = float(thr_default) - float(thr_eer)

        return Response({
            "auc": metrics.get("auc"),
            "eer": metrics.get("eer"),
            "threshold": thr_eer,
            "threshold_default": thr_default,
            "threshold_diff": threshold_diff,
            "fpr": roc_data.get("fpr") if roc_data else None,
            "tpr": roc_data.get("tpr") if roc_data else None,
            "thresholds": roc_data.get("thresholds") if roc_data else None,
        })


class ThresholdConfigView(APIView):
    """管理员查看 / 修改当前声纹验证默认阈值"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({"threshold": get_effective_threshold()})

    def post(self, request):
        serializer = ThresholdConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["threshold"]
        settings.VOICE_VERIFY_THRESHOLD = float(value)
        return Response({"threshold": get_effective_threshold()})
