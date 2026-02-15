import os
import time
import logging

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from .models import VoiceTemplate, VerifyLog, EnrollLog
from .model_loader import get_model
from .view_utils import get_client_ip, validate_audio_file
from model.enroll import enroll as model_enroll
from model.verify_demo import verify as model_verify

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
            model_enroll(user_id, saved_paths)

            VoiceTemplate.objects.update_or_create(
                user=request.user,
                defaults={
                    "template_path": os.path.join(os.fspath(settings.VOICEPRINTS_DIR), "user_templates.npy"),
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
