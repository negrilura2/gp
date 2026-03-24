import os
import time
import logging

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from ..models import VoiceTemplate, EnrollLog, VerifyLog
from ..model_loader import get_service # Use the new service accessor
from ..serializers import get_effective_threshold
from ..view_utils import (
    get_client_ip,
    validate_audio_file,
    get_default_feature_dir_for_eval,
)
from ..utils.openclaw import claw_client

logger = logging.getLogger("api")


class EnrollView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user_id = request.data.get("user_id", "").strip()
        if not request.user.is_staff or not user_id:
            user_id = request.user.username
        client_ip = get_client_ip(request)
        files = request.FILES.getlist("files")

        if not files:
            return Response({"error": "请至少上传一个音频文件"}, status=400)

        try:
            for f in files:
                validate_audio_file(f)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        saved_paths = []
        user_dir = os.path.join(os.fspath(settings.ENROLL_DIR), user_id)
        os.makedirs(user_dir, exist_ok=True)

        for f in files:
            fname = f"{int(time.time() * 1000)}_{f.name}"
            path = os.path.join(user_dir, fname)
            with open(path, "wb") as out:
                for chunk in f.chunks():
                    out.write(chunk)
            saved_paths.append(path)

        try:
            # Use VoiceService for enrollment
            service = get_service()
            result = service.enroll(user_id, saved_paths)
            
            if result.get("status") == "error":
                raise RuntimeError(result.get("error"))

            VoiceTemplate.objects.update_or_create(
                user=request.user,
                defaults={
                    "template_path": "vector_store", # Use VectorStore
                    "embedding_count": len(saved_paths),
                },
            )

            EnrollLog.objects.create(
                user=request.user,
                username=user_id,
                wav_count=len(saved_paths),
                client_ip=client_ip,
                success=True,
            )

            logger.info(f"声纹注册成功: {user_id}, {len(saved_paths)} 条音频")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"声纹注册失败: {user_id}, {e}\n{tb}")
            EnrollLog.objects.create(
                user=request.user,
                username=user_id,
                wav_count=len(saved_paths),
                client_ip=client_ip,
                success=False,
                error_msg=f"{str(e)}\n{tb}",
            )
            return Response({"error": f"{str(e)}\n{tb}"}, status=500)

        return Response(
            {
                "status": "enrolled",
                "user": user_id,
                "wav_count": len(saved_paths),
            }
        )


class VerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        try:
            thr_raw = request.data.get("threshold", None)
            if thr_raw is None or thr_raw == "":
                thr = settings.VOICE_VERIFY_THRESHOLD
            else:
                thr = float(thr_raw)
        except (TypeError, ValueError):
            return Response({"error": "threshold 必须是数字"}, status=400)
        if not (0 < thr < 1):
            return Response({"error": "threshold 必须在 0~1 之间"}, status=400)
        f = request.FILES.get("file")
        client_ip = get_client_ip(request)

        if not f:
            return Response({"error": "请上传一个音频文件"}, status=400)

        try:
            validate_audio_file(f)
        except ValueError as e:
            return Response({"error": str(e)}, status=400)

        upload_dir = os.fspath(settings.RECORDINGS_DIR)
        os.makedirs(upload_dir, exist_ok=True)
        fname = f"{int(time.time() * 1000)}_{f.name}"
        path = os.path.join(upload_dir, fname)
        with open(path, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)

        try:
            # Use VoiceService for verification
            service = get_service()
            verify_result = service.verify(path, threshold=thr)
            
            if verify_result.get("status") == "error":
                # Handle specific error cases if needed, e.g. FileNotFound
                # For now we propagate the error message
                error_msg = verify_result.get("error")
                if "FileNotFound" in error_msg or "模板不存在" in error_msg:
                     raise FileNotFoundError(error_msg)
                raise RuntimeError(error_msg)

            best_spk = verify_result["predicted_user"]
            best_score = verify_result.get("best_score", 0.0)
            result = verify_result["result"]

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

        matched_user = User.objects.filter(username=str(best_spk)).first()
        user_info = None
        # 如果 result 是布尔值 True/False，转换为 "ACCEPT"/"REJECT"
        if isinstance(result, bool):
            result = "ACCEPT" if result else "REJECT"
        door_state = "OPEN" if result == "ACCEPT" else "CLOSED"

        if matched_user and result == "ACCEPT":
            user_info = {
                "id": matched_user.id,
                "username": matched_user.username,
                "email": matched_user.email,
                "is_staff": matched_user.is_staff,
            }
            # OpenClaw 通知：验证成功（可选，防止打扰可设为仅重要人员或时段）
            claw_client.send_notification(
                f"✅ 声纹验证通过\n用户: {matched_user.username}\n置信度: {best_score:.2f}"
            )

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
        
        if result == "REJECT":
            # OpenClaw 通知：验证失败（陌生人入侵警告）
            claw_client.send_notification(
                f"🚨 声纹验证失败 (潜在入侵)\n匹配用户: {best_spk}\n置信度: {best_score:.2f} (阈值 {thr})\n来源IP: {client_ip}"
            )

        logger.info(f"声纹验证: {best_spk} score={best_score:.4f} => {result}")
        return Response(
            {
                "predicted_user": str(best_spk),
                "score": float(best_score),
                "result": result,
                "door_state": door_state,
                "user_info": user_info,
                "threshold": thr,
            }
        )


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
