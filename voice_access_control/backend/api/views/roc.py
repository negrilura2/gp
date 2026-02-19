import os
import json

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from ..serializers import ThresholdConfigSerializer, get_effective_threshold
from ..model_loader import get_model_path
from ..view_utils import (
    IsAdminUser,
    count_files,
    get_latest_file_path,
    load_json_if_exists,
    sanitize_json_value,
    EVAL_STATUS_LOCK,
    _read_eval_status,
    _set_eval_status,
    _start_eval_thread,
    get_eval_thread,
    get_default_feature_dir_for_eval,
    get_feature_dir_for_model,
)


class RocEvaluateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        model_name = request.data.get("name")
        models_dir = os.fspath(settings.MODELS_DIR)
        model_path = None
        if model_name:
            candidate = os.path.join(models_dir, model_name)
            if os.path.isfile(candidate):
                model_path = candidate
            else:
                return Response({"error": "模型不存在"}, status=status.HTTP_404_NOT_FOUND)
        else:
            model_path = get_model_path()
        if not model_path or not os.path.isfile(model_path):
            model_path = get_latest_file_path(models_dir, {".pth", ".pt", ".onnx"})
        if not model_path or not os.path.isfile(model_path):
            return Response({"status": "failed", "error": "模型文件不存在"})
        feature_dir = get_feature_dir_for_model(model_path)
        if count_files(feature_dir, {".npy"}) == 0:
            return Response({"status": "failed", "error": "特征文件为空，无法评估"})
        with EVAL_STATUS_LOCK:
            status_payload = _read_eval_status()
            if status_payload.get("status") == "running":
                eval_thread = get_eval_thread()
                if eval_thread is not None and eval_thread.is_alive():
                    return Response(status_payload)
                _set_eval_status("failed", error="评估进程异常终止")
            _start_eval_thread(model_path, feature_dir)
            return Response({"status": "running", "model": os.path.basename(model_path), "feature_dir": feature_dir})


class RocEvaluateStatusView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(_read_eval_status())


class RocView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        reports_dir = os.fspath(settings.REPORTS_DIR)
        backend_dir = os.path.join(reports_dir, "archive", "backend_responses")
        eer_path = os.path.join(backend_dir, "eer_threshold.json")
        roc_points_path = os.path.join(backend_dir, "roc_points.json")
        det_points_path = os.path.join(backend_dir, "det_points.json")
        mindcf_path = os.path.join(backend_dir, "mindcf.json")
        score_dist_path = os.path.join(backend_dir, "score_dist.json")
        calib_path = os.path.join(backend_dir, "calibration.json")

        if not os.path.exists(eer_path):
            return Response({"error": "eer_threshold.json not found, 请先运行阈值评估脚本"}, status=404)

        with open(eer_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)

        roc_data = load_json_if_exists(roc_points_path)

        thr_recommended = metrics.get("threshold")
        thr_eer = metrics.get("threshold_eer") or metrics.get("threshold")
        thr_mindcf = metrics.get("threshold_mindcf")
        thr_default = getattr(settings, "VOICE_VERIFY_THRESHOLD", None)
        threshold_diff = None
        if thr_recommended is not None and thr_default is not None:
            threshold_diff = float(thr_default) - float(thr_recommended)
        status_payload = _read_eval_status()

        det_data = load_json_if_exists(det_points_path)
        mindcf_data = load_json_if_exists(mindcf_path)
        score_dist_data = load_json_if_exists(score_dist_path)
        calib_data = load_json_if_exists(calib_path)

        payload = {
            "auc": metrics.get("auc"),
            "eer": metrics.get("eer"),
            "threshold": thr_recommended,
            "threshold_eer": thr_eer,
            "threshold_mindcf": thr_mindcf,
            "mindcf": metrics.get("mindcf"),
            "p_target": metrics.get("p_target"),
            "c_miss": metrics.get("c_miss"),
            "c_fa": metrics.get("c_fa"),
            "threshold_default": thr_default,
            "threshold_diff": threshold_diff,
            "fpr": roc_data.get("fpr") if roc_data else None,
            "tpr": roc_data.get("tpr") if roc_data else None,
            "thresholds": roc_data.get("thresholds") if roc_data else None,
            "det": det_data,
            "mindcf_data": mindcf_data,
            "score_dist": score_dist_data,
            "calibration": calib_data,
            "model": status_payload.get("model"),
        }
        return Response(sanitize_json_value(payload))


class ThresholdConfigView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({"threshold": get_effective_threshold()})

    def post(self, request):
        serializer = ThresholdConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["threshold"]
        settings.VOICE_VERIFY_THRESHOLD = float(value)
        return Response({"threshold": get_effective_threshold()})
