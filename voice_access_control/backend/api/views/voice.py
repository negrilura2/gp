import os
import time
import logging

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions

from ..models import VoiceTemplate, EnrollLog, VerifyLog
from ..model_loader import get_model, get_feature_type, get_feat_dim, get_n_mels, get_device, get_model_path
from ..serializers import get_effective_threshold
from ..view_utils import (
    get_client_ip,
    validate_audio_file,
    get_default_feature_dir_for_eval,
)
from voice_engine.enroll import enroll as model_enroll
from voice_engine.verify_demo import verify as model_verify

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
            model_path = get_model_path()
            model, device, feature_type, n_mels = get_model()
            model_enroll(
                user_id,
                saved_paths,
                model_path=model_path,
                feature_type=feature_type,
                n_mels=n_mels,
            )

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
            model, device, feature_type, n_mels = get_model()
            # 临时修正：直接调用模型进行推理，而不是使用封装好的 model_verify，因为 model_verify 内部可能没有传递所有参数
            # 或者我们需要检查 model_verify 的实现。
            # 这里我们假设 model_verify 是正确的，但需要确保传递所有参数。
            
            # 检查 voice_engine.verify_demo.verify 的签名
            # def verify(wav_path, threshold=0.25, model_path=None, model=None, device=None, feature_type=None, n_mels=80):
            
            best_spk, best_score, result = model_verify(
                path,
                threshold=thr,
                model=model,
                device=device,
                feature_type=feature_type,
                n_mels=n_mels,
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
