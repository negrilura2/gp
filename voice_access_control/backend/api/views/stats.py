import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, Avg, Max, Min
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response

from ..models import VerifyLog, EnrollLog, VoiceTemplate
from ..serializers import get_effective_threshold
from ..view_utils import IsAdminUser, count_files, get_latest_file_info


class StatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        mode = request.query_params.get("mode", "").lower()

        # === 1. 基础数据 ===
        
        # 用户统计 (排除管理员)
        user_count = User.objects.filter(is_staff=False, is_superuser=False).count()
        enroll_count = EnrollLog.objects.values('username').distinct().count()

        # 日志统计
        total_logs = VerifyLog.objects.count()
        accept_count = VerifyLog.objects.filter(result="ACCEPT").count()
        verify_accept_rate = round(accept_count / total_logs, 4) if total_logs > 0 else 0
        
        # === 2. 意图分布 (Intent Distribution) - NEW ===
        # 统计不同意图的占比：开门、开灯、查询知识库、纯验证
        intent_stats = (
            VerifyLog.objects.values('intent')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # === 3. 来源分布 (Source Distribution) - NEW ===
        # 统计决策来源：Local NLU (Edge) vs Cloud Agent (Cloud)
        source_stats = (
            VerifyLog.objects.values('source')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # === 4. 延迟性能 (Latency Heatmap data) - NEW ===
        # 获取最近 50 条记录的延迟数据，用于前端绘制性能热力图或散点图
        latency_data = (
            VerifyLog.objects.all()
            .order_by('-timestamp')[:50]
            .values('timestamp', 'latency_ms', 'source', 'intent')
        )

        # === 5. 每日趋势 (Daily Trends) ===
        daily = (
            VerifyLog.objects.annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(
                total=Count("id"),
                avg_score=Avg("score"),
                # 统计每天的 AI 交互次数 (intent != verify_only)
                ai_interaction_count=Count("id", filter=~models.Q(intent="verify_only")),
            )
            .order_by("date")
        )
        
        daily_data = [
            {
                "date": str(d["date"]),
                "total": d["total"],
                "avg_score": round(d["avg_score"], 4) if d["avg_score"] else 0,
                "ai_interactions": d["ai_interaction_count"]
            }
            for d in daily
        ]

        # === 6. 聚合响应 ===
        return Response({
            "summary": {
                "total_users": user_count,
                "enrolled_users": enroll_count,
                "total_verifications": total_logs,
                "verify_accept_rate": verify_accept_rate,
            },
            "intent_distribution": list(intent_stats),
            "source_distribution": list(source_stats),
            "latency_history": list(latency_data),
            "daily_trends": daily_data,
        })


class DashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.filter(is_staff=False, is_superuser=False).count()
        admin_users = User.objects.filter(models.Q(is_staff=True) | models.Q(is_superuser=True)).count()
        enrolled_users = VoiceTemplate.objects.filter(user__is_staff=False, user__is_superuser=False).values("user").distinct().count()

        verify_stats = VerifyLog.objects.aggregate(
            total=Count("id"),
            accept=Count("id", filter=models.Q(result="ACCEPT")),
            reject=Count("id", filter=models.Q(result="REJECT")),
        )
        verify_total = verify_stats.get("total") or 0
        verify_accept = verify_stats.get("accept") or 0
        verify_reject = verify_stats.get("reject") or 0
        verify_rate = round(verify_accept / verify_total, 4) if verify_total else 0

        enroll_stats = EnrollLog.objects.aggregate(
            total=Count("id"),
            success=Count("id", filter=models.Q(success=True)),
        )
        enroll_total = enroll_stats.get("total") or 0
        enroll_success = enroll_stats.get("success") or 0
        enroll_rate = round(enroll_success / enroll_total, 4) if enroll_total else 0

        verify_daily = (
            VerifyLog.objects.annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(total=Count("id"))
            .order_by("date")
        )
        enroll_daily = (
            EnrollLog.objects.annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(total=Count("id"))
            .order_by("date")
        )

        model_info = get_latest_file_info(os.fspath(settings.MODELS_DIR), {".pth", ".pt", ".onnx"})

        return Response(
            {
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
                    "raw_wav": count_files(os.fspath(settings.RAW_DIR), {".wav"}),
                    "processed_wav": count_files(os.fspath(settings.PROCESSED_DIR), {".wav"}),
                    "feature_files": count_files(os.fspath(settings.FEATURES_DIR), {".npy"}),
                    "voiceprints": VoiceTemplate.objects.count(), # Use DB count instead of file count
                    "recordings": count_files(
                        os.fspath(settings.RECORDINGS_DIR),
                        {".wav", ".flac", ".mp3", ".ogg", ".m4a"},
                    ),
                },
                "trend": {
                    "verify_daily": [{"date": str(d["date"]), "total": d["total"]} for d in verify_daily],
                    "enroll_daily": [{"date": str(d["date"]), "total": d["total"]} for d in enroll_daily],
                },
                "model": {
                    "count": count_files(os.fspath(settings.MODELS_DIR), {".pth", ".pt", ".onnx"}),
                    "latest_name": model_info["name"],
                    "latest_mtime": model_info["mtime"],
                },
            }
        )
