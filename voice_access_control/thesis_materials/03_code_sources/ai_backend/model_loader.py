
"""
模型单例加载器 (Adapter for VoiceService).
在 Django 启动时加载一次模型，后续所有请求共享同一个模型实例，避免重复加载。
"""
import os
import threading
import time
import logging

import httpx
import numpy as np

# 项目根目录
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

import sys
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.service import VoiceService

logger = logging.getLogger("api")
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "").strip()


class HttpVoiceService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.model_path = None
        self.feature_type = "unknown"
        self.n_mels = 40
        self.feat_dim = 192
        self.device = "remote"
        self._sync_config()

    def _sync_config(self):
        """Fetch configuration from remote service to ensure consistency."""
        try:
            url = f"{self.base_url}/health"
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                self.model_path = data.get("model_path")
                self.device = data.get("device", "remote")
                self.feature_type = data.get("feature_type", "unknown")
                self.n_mels = data.get("n_mels", 80)
                # Note: feat_dim might not be in health check, but we can infer or add it later if needed.
                # For now, 192 is standard for ECAPA-TDNN.
        except Exception as e:
            logger.warning(f"Failed to sync config from AI Service: {e}")

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
            emb_list = data.get("embedding")
            if emb_list:
                return np.array(emb_list)
            return None
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

def get_voice_feature_with_retry(username, retries=3, delay=0.2):
    """
    Robust feature retrieval with retry logic for consistency.
    Handles differences between Local and Http service returns.
    """
    service = get_service()
    
    # Helper to standardize return to np.ndarray
    def _fetch():
        try:
            emb = service.get_feature(username)
            if emb is None:
                return None
            if isinstance(emb, list):
                emb = np.array(emb)
            if isinstance(emb, np.ndarray) and emb.size > 0:
                return emb
            return None
        except Exception as e:
            logger.warning(f"Error fetching feature for {username}: {e}")
            return None

    # First attempt
    emb = _fetch()
    if emb is not None:
        return emb
        
    # Retry loop
    for i in range(retries):
        time.sleep(delay)
        emb = _fetch()
        if emb is not None:
            logger.info(f"Voiceprint found for {username} after retry {i+1}")
            return emb
            
    return None

def get_model(model_path=None, n_mels=None):
    """
    Deprecated: Use get_service() instead.
    Maintained for backward compatibility with older views.
    """
    service = get_service()
    if isinstance(service, HttpVoiceService):
        # Mock return for HttpService to avoid breaking legacy code
        return None, "cpu", "unknown", 80
    return service.model, service.device, service.feature_type, service.n_mels

def get_model_path():
    service = get_service()
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
