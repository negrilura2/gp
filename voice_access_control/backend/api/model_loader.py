"""
模型单例加载器 (Adapter for VoiceService)。
在 Django 启动时加载一次模型，后续所有请求共享同一个模型实例，避免重复加载。
"""
import os
import threading

import httpx

# 项目根目录
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

import sys
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.service import VoiceService

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "").strip()


class HttpVoiceService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.model_path = None

    def _post_files(self, path, data, files):
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, data=data, files=files)
        resp.raise_for_status()
        return resp.json()

    def enroll(self, user_id, wav_paths):
        files = []
        try:
            for p in wav_paths:
                f = open(p, "rb")
                files.append(
                    ("files", (os.path.basename(p), f, "audio/wav"))
                )
            return self._post_files(
                "/enroll",
                {"user_id": user_id},
                files,
            )
        finally:
            for _, (_, f, _) in files:
                try:
                    f.close()
                except Exception:
                    pass

    def verify(self, wav_path, threshold=None):
        files = []
        f = None
        try:
            f = open(wav_path, "rb")
            files.append(
                ("file", (os.path.basename(wav_path), f, "audio/wav"))
            )
            data = {}
            if threshold is not None:
                data["threshold"] = str(threshold)
            return self._post_files("/verify", data, files)
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass

    def get_feature(self, user_id):
        url = f"{self.base_url}/voiceprint/{user_id}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            # Expecting {"user_id": ..., "embedding": [list]}
            return data.get("embedding")
        except Exception:
            return None

    def delete_feature(self, user_id):
        url = f"{self.base_url}/voiceprint/{user_id}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.delete(url)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except Exception:
            return False

    def reload(self, model_path=None, device=None):
        data = {}
        if model_path:
            data["model_path"] = model_path
            self.model_path = model_path
        if device:
            data["device"] = device
        url = f"{self.base_url}/reload"
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, data=data)
        resp.raise_for_status()
        return resp.json()


_service = None
_lock = threading.Lock()

def get_service():
    """
    获取 VoiceService 单例。
    """
    global _service
    if _service is None:
        with _lock:
            if _service is None:
                if AI_SERVICE_URL:
                    _service = HttpVoiceService(AI_SERVICE_URL)
                else:
                    _service = VoiceService.get_instance()
    return _service

def get_model(model_path=None, n_mels=None):
    """
    Deprecated: Use get_service() instead.
    Maintained for backward compatibility with older views.
    """
    service = get_service()
    if isinstance(service, HttpVoiceService):
        url = f"{AI_SERVICE_URL.rstrip('/')}/health"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return None, data.get("device"), None, data.get("n_mels")
    return service.model, service.device, service.feature_type, service.n_mels

def get_model_path():
    service = get_service()
    if isinstance(service, HttpVoiceService):
        return service.model_path
    return service.model_path

def set_model_path(model_path):
    global _service
    with _lock:
        if AI_SERVICE_URL:
            if _service is None or not isinstance(_service, HttpVoiceService):
                _service = HttpVoiceService(AI_SERVICE_URL)
            _service.reload(model_path=model_path)
        else:
            _service = VoiceService.reload(model_path=model_path)

def get_feature_type():
    service = get_service()
    return service.feature_type

def get_feat_dim():
    service = get_service()
    return service.feat_dim

def get_n_mels():
    service = get_service()
    return service.n_mels

def get_device():
    service = get_service()
    return service.device
    _model_path = model_path
