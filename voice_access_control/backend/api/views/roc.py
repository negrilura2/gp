import os
import json

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

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
        norm_method = request.data.get("norm_method", "none")
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
            candidate = get_latest_file_path(models_dir, {".pth", ".pt", ".onnx"})
            if candidate:
                model_path = candidate
                
        if not model_path or not os.path.isfile(model_path):
            return Response({"status": "failed", "error": "模型文件不存在"})
            
        feature_dir = get_feature_dir_for_model(model_path)
        if count_files(feature_dir, {".npy"}) == 0:
            # Try appending mfcc_delta if count is 0
            candidate = os.path.join(feature_dir, "mfcc_delta")
            if os.path.isdir(candidate) and count_files(candidate, {".npy"}) > 0:
                feature_dir = candidate
            elif count_files(feature_dir, {".npy"}) == 0:
                 return Response({"status": "failed", "error": "特征文件为空，无法评估"})
        
        with EVAL_STATUS_LOCK:
            status_payload = _read_eval_status()
            if status_payload.get("status") == "running":
                eval_thread = get_eval_thread()
                if eval_thread is not None and eval_thread.is_alive():
                    return Response(status_payload)
                _set_eval_status("failed", error="评估进程异常终止")
            
            # Start evaluation thread
            from ..view_utils import _start_eval_thread
            _start_eval_thread(model_path, feature_dir, norm_method=norm_method)
            return Response({"status": "running", "model": os.path.basename(model_path), "feature_dir": feature_dir})


class RocEvaluateStatusView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(_read_eval_status())


class RocView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        reports_dir = os.fspath(settings.REPORTS_DIR)
        
        # Determine backend_dir based on query param
        norm_method = request.query_params.get("norm_method", "none")
        # Validate method string to prevent directory traversal
        if norm_method not in ["none", "znorm", "tnorm", "snorm"]:
            norm_method = "none"
            
        backend_dir = os.path.join(reports_dir, "backend_responses", norm_method)
        
        # If specific method dir doesn't exist, try falling back to legacy structure (only for 'none')
        # Since we cleaned up, legacy might not be there, but good to check archive if needed?
        # For now, if not found, we just let it fail or check archive.
        if not os.path.isdir(backend_dir) and norm_method == "none":
             legacy_dir = os.path.join(reports_dir, "archive", "backend_responses")
             if os.path.exists(os.path.join(legacy_dir, "eer_threshold.json")):
                 backend_dir = legacy_dir
        
        eer_path = os.path.join(backend_dir, "eer_threshold.json")
        roc_points_path = os.path.join(backend_dir, "roc_points.json")
        det_points_path = os.path.join(backend_dir, "det_points.json")
        mindcf_path = os.path.join(backend_dir, "mindcf.json")
        score_dist_path = os.path.join(backend_dir, "score_dist.json")
        calib_path = os.path.join(backend_dir, "calibration.json")

        if not os.path.exists(eer_path):
            return Response({"error": f"尚未生成 {norm_method} 评估数据"}, status=404)

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
        
        # Construct score_norm payload for frontend compatibility
        score_norm_payload = None
        if metrics.get("score_norm"):
             score_norm_payload = {
                "metrics": metrics,
                "fpr": roc_data.get("fpr") if roc_data else None,
                "tpr": roc_data.get("tpr") if roc_data else None,
                "thresholds": roc_data.get("thresholds") if roc_data else None,
                "det": det_data,
                "mindcf_data": mindcf_data,
                "score_dist": score_dist_data,
                "calibration": calib_data,
            }

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
            "score_norm": score_norm_payload,
            "method": norm_method
        }
        resp = Response(sanitize_json_value(payload))
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp["Pragma"] = "no-cache"
        return resp


class ThresholdConfigView(APIView):
    """
    阈值配置接口：
    - GET：任何客户端（包括 AI 服务）都可以读取当前阈值
    - POST：仅管理员可修改
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        return Response({"threshold": get_effective_threshold()})

    def post(self, request):
        serializer = ThresholdConfigSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["threshold"]
        settings.VOICE_VERIFY_THRESHOLD = float(value)
        return Response({"threshold": get_effective_threshold()})