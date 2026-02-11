from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.contrib.auth.models import User
from .models import VoiceTemplate, VerifyLog
from .serializers import VoiceTemplateSerializer, VerifyLogSerializer
import os, time

# 引入你现有的 enroll/verify 方法（包内导入）
from model.enroll import enroll as model_enroll
from model.verify_demo import verify as model_verify  # verify(wav_path, model_path=None, threshold=0.75)

class EnrollView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # 可暂时放开

    def post(self, request):
        """
        接受 form-data:
        - user_id (username)
        - files: wav 文件数组 或 提供 wav_paths 列表（路径）
        """
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error":"user_id required"}, status=400)

        # 如果上传文件
        files = request.FILES.getlist('files')
        saved_paths = []
        os.makedirs('data/enroll', exist_ok=True)
        user_dir = os.path.join('data','enroll', user_id)
        os.makedirs(user_dir, exist_ok=True)

        for f in files:
            fname = f"{int(time.time()*1000)}_{f.name}"
            path = os.path.join(user_dir, fname)
            with open(path, 'wb') as out:
                for chunk in f.chunks():
                    out.write(chunk)
            saved_paths.append(path)

        if not saved_paths:
            return Response({"error":"no files uploaded"}, status=400)

        # 调用 model.enroll：它接收 user_id 和 wav_paths 列表
        try:
            model_enroll(user_id, saved_paths)
            # 保存到 VoiceTemplate 表（保存 template path）
            # model.enroll 保存模板到 data/voiceprints/user_templates.npy
            vt = VoiceTemplate(user=User.objects.get(username=user_id), template_path='data/voiceprints/user_templates.npy')
            vt.save()
        except Exception as e:
            return Response({"error": str(e)}, status=500)

        return Response({"status":"enrolled", "user": user_id})

class VerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """
        form-data:
        - file: wav
        - threshold (optional)
        """
        thr = float(request.data.get('threshold', 0.75))
        f = request.FILES.get('file')
        if not f:
            return Response({"error":"file required"}, status=400)

        os.makedirs('data/verify_uploads', exist_ok=True)
        fname = f"{int(time.time()*1000)}_{f.name}"
        path = os.path.join('data','verify_uploads', fname)
        with open(path, 'wb') as out:
            for chunk in f.chunks():
                out.write(chunk)

        try:
            best_spk, best_score, result = model_verify(path, model_path="models/ecapa_best.pth", threshold=thr)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

        # log record
        log = VerifyLog(wav_path=path, predicted_user=str(best_spk), score=float(best_score), result=result)
        log.save()

        return Response({"predicted_user": str(best_spk), "score": float(best_score), "result": result})
