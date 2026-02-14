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

from model.ecapa_tdnn import LightECAPA

_model = None
_device = None
_lock = threading.Lock()

DEFAULT_MODEL_PATH = os.path.join(ROOT, "models", "ecapa_best.pth")
_model_path = DEFAULT_MODEL_PATH


def get_model(model_path=None):
    """
    获取全局模型单例。线程安全。

    返回：
        (model, device)
    """
    global _model, _device, _model_path

    if _model is not None:
        return _model, _device

    with _lock:
        # 双重检查
        if _model is not None:
            return _model, _device

        model_path = model_path or _model_path or DEFAULT_MODEL_PATH
        _model_path = model_path
        _device = "cuda" if torch.cuda.is_available() else "cpu"

        print(f"[ModelLoader] 加载模型: {model_path} -> {_device}")
        _model = LightECAPA(feat_dim=39, emb_dim=192, n_speakers=None).to(_device)
        state = torch.load(model_path, map_location=_device)
        _model.load_state_dict(state, strict=False)
        _model.eval()
        print(f"[ModelLoader] 模型加载完成 ✅")

        return _model, _device


def get_model_path():
    return _model_path or DEFAULT_MODEL_PATH


def set_model_path(model_path):
    global _model, _device, _model_path
    _model = None
    _device = None
    _model_path = model_path
