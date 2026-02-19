"""
模型单例加载器。
在 Django 启动时加载一次模型，后续所有请求共享同一个模型实例，避免重复加载。
"""
import os
import torch
import threading

# 项目根目录
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

import sys
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.ecapa_tdnn import LightECAPA
from voice_engine.config import (
    DEFAULT_MODEL_PATH,
    DEFAULT_N_MELS,
    FEATURE_TYPE_MFCC,
    FEATURE_TYPE_MFCC_DELTA,
    FEATURE_TYPE_LOGMEL,
    DEFAULT_DEVICE
)
from voice_engine.features import infer_feature_type_from_feat_dim

_model = None
_device = None
_feature_type = None
_feat_dim = None
_n_mels = None
_lock = threading.Lock()
_model_path = DEFAULT_MODEL_PATH


def _infer_feature_type_from_name(model_path):
    name = os.path.basename(model_path).lower()
    if FEATURE_TYPE_MFCC_DELTA in name:
        return FEATURE_TYPE_MFCC_DELTA
    if FEATURE_TYPE_LOGMEL in name:
        return FEATURE_TYPE_LOGMEL
    if FEATURE_TYPE_MFCC in name:
        return FEATURE_TYPE_MFCC
    return None


def get_model(model_path=None, n_mels=None):
    """
    获取全局模型单例。线程安全。

    返回：
        (model, device, feature_type, n_mels)
    """
    global _model, _device, _model_path, _feature_type, _feat_dim, _n_mels

    if _model is not None:
        return _model, _device, _feature_type, _n_mels

    with _lock:
        # 双重检查
        if _model is not None:
            return _model, _device, _feature_type, _n_mels

        model_path = model_path or _model_path or DEFAULT_MODEL_PATH
        _model_path = model_path
        _device = DEFAULT_DEVICE if torch.cuda.is_available() else "cpu"
        _n_mels = n_mels or _n_mels or DEFAULT_N_MELS

        print(f"[ModelLoader] 加载模型: {model_path} -> {_device}")
        state = torch.load(model_path, map_location=_device)
        feat_dim = 39
        w = state.get("layer1.conv.weight")
        if w is not None and w.ndim == 3:
            feat_dim = int(w.shape[1])
        _feat_dim = feat_dim
        feature_type = _infer_feature_type_from_name(model_path)
        if feature_type is None:
            feature_type = infer_feature_type_from_feat_dim(feat_dim, _n_mels)
        if feature_type == FEATURE_TYPE_LOGMEL:
            _n_mels = feat_dim
        _feature_type = feature_type
        _model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(_device)
        _model.load_state_dict(state, strict=False)
        _model.eval()
        print(f"[ModelLoader] 模型加载完成 ✅")

        return _model, _device, _feature_type, _n_mels


def get_model_path():
    return _model_path or DEFAULT_MODEL_PATH


def set_model_path(model_path):
    global _model, _device, _model_path, _feature_type, _feat_dim, _n_mels
    _model = None
    _device = None
    _feature_type = None
    _feat_dim = None
    _n_mels = None
    _model_path = model_path
    print(f"[ModelLoader] 更新模型路径: {model_path}，已重置单例。")


def get_feature_type():
    global _feature_type
    if _feature_type is None:
        get_model()  # 触发加载
    return _feature_type


def get_feat_dim():
    global _feat_dim
    if _feat_dim is None:
        get_model()
    return _feat_dim


def get_n_mels():
    global _n_mels
    if _n_mels is None:
        get_model()
    return _n_mels


def get_device():
    global _device
    if _device is None:
        get_model()
    return _device
    _model_path = model_path
