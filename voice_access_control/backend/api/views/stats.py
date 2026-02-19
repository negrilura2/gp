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

        daily = (
            VerifyLog.objects.annotate(date=TruncDate("timestamp"))
            .values("date")
            .annotate(
                total=Count("id"),
                avg_score=Avg("score"),
                accept_count=Count("id", filter=models.Q(result="ACCEPT")),
                reject_count=Count("id", filter=models.Q(result="REJECT")),
            )
            .order_by("date")
        )
        daily_data = [
            {
                "date": str(d["date"]),
                "total": d["total"],
                "avg_score": round(d["avg_score"], 4) if d["avg_score"] else 0,
                "accept_rate": round(d["accept_count"] / d["total"], 4) if d["total"] else 0,
            }
            for d in daily
        ]

        result_stats = VerifyLog.objects.aggregate(
            accept=Count("id", filter=models.Q(result="ACCEPT")),
            reject=Count("id", filter=models.Q(result="REJECT")),
        )
        accept_count = result_stats.get("accept") or 0
        reject_count = result_stats.get("reject") or 0
        total_count = accept_count + reject_count
        accept_rate = round(accept_count / total_count, 4) if total_count else 0

        now = timezone.now()
        last_7_qs = VerifyLog.objects.filter(timestamp__gte=now - timedelta(days=7))
        last_30_qs = VerifyLog.objects.filter(timestamp__gte=now - timedelta(days=30))

        def _window_summary(qs):
            stats = qs.aggregate(
                total=Count("id"),
                accept=Count("id", filter=models.Q(result="ACCEPT")),
            )
            total = stats.get("total") or 0
            if total == 0:
                return {"total": 0, "accept_rate": 0}
            acc = stats.get("accept") or 0
            return {
                "total": total,
                "accept_rate": round(acc / total, 4),
            }

        window_summary = {
            "last_7_days": _window_summary(last_7_qs),
            "last_30_days": _window_summary(last_30_qs),
        }

        score_stats = {"max": 0, "min": 0, "avg": 0, "median": 0}
        all_qs = VerifyLog.objects.all()
        total_scores = all_qs.count()
        if total_scores > 0:
            agg = all_qs.aggregate(
                max_score=Max("score"),
                min_score=Min("score"),
                avg_score=Avg("score"),
            )
            ordered_scores = all_qs.order_by("score").values_list("score", flat=True)
            mid = (total_scores - 1) // 2
            if total_scores % 2 == 1:
                median = float(ordered_scores[mid])
            else:
                left = float(ordered_scores[mid])
                right = float(ordered_scores[mid + 1])
                median = float((left + right) / 2.0)
            score_stats = {
                "max": float(agg["max_score"]) if agg["max_score"] is not None else 0,
                "min": float(agg["min_score"]) if agg["min_score"] is not None else 0,
                "avg": float(agg["avg_score"]) if agg["avg_score"] is not None else 0,
                "median": median,
            }

        total_users = User.objects.count()
        enrolled_users = VoiceTemplate.objects.values("user").distinct().count()

        if mode == "echarts":
            x_axis = [d["date"] for d in daily_data]
            return Response(
                {
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
                }
            )

        return Response(
            {
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
            }
        )


class DashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.count()
        admin_users = User.objects.filter(is_staff=True).count()
        enrolled_users = VoiceTemplate.objects.values("user").distinct().count()

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
                    "voiceprints": count_files(os.fspath(settings.VOICEPRINTS_DIR), {".npy"}),
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
