"""
模型单例加载器 (Adapter for VoiceService)。
在 Django 启动时加载一次模型，后续所有请求共享同一个模型实例，避免重复加载。
"""
import os
import threading

# 项目根目录
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

import sys
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.service import VoiceService
from voice_engine.config import DEFAULT_MODEL_PATH

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
                _service = VoiceService.get_instance()
    return _service

def get_model(model_path=None, n_mels=None):
    """
    Deprecated: Use get_service() instead.
    Maintained for backward compatibility with older views.
    """
    service = get_service()
    # If model_path changed, we might need to reload, but VoiceService is singleton.
    # For now, return exposed internals.
    return service.model, service.device, service.feature_type, service.n_mels

def get_model_path():
    service = get_service()
    return service.model_path

def set_model_path(model_path):
    # This is tricky with singleton. We should update the singleton.
    # But VoiceService currently loads in __init__.
    # We might need to force reload.
    global _service
    with _lock:
        # Re-instantiate service with new path
        # Note: This is a bit of a hack against the Singleton pattern of VoiceService.
        # Ideally VoiceService should have a 'reload(path)' method.
        # For now, we just reset the internal singleton of VoiceService if we could, 
        # or we just create a new instance and assign it to _service.
        # But VoiceService.get_instance() will still return the old one if we don't clear it.
        VoiceService._instance = None 
        _service = VoiceService(model_path=model_path)

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
