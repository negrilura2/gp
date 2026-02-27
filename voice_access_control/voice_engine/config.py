"""
Voice Engine Configuration
统一管理声纹识别引擎的全局配置参数，支持环境变量配置 (Fix Dual Source of Truth)。
"""
import os
from pathlib import Path

# 尝试加载环境配置
# 策略：
# 1. 优先检查 APP_ENV 环境变量 (local/docker)
# 2. 如果是 docker (通常由 docker-compose 设置 APP_ENV=docker)，加载 .env.docker
# 3. 否则默认加载 .env.local (本地开发)
# 4. 如果都没有，加载 .env (兼容旧习惯)
try:
    from dotenv import load_dotenv
    
    app_env = os.getenv("APP_ENV", "local")
    if os.name == "nt" and app_env == "docker":
        app_env = "local"
    env_file = f".env.{app_env}"
    
    # 路径计算：从 voice_engine/config.py 上两级找到项目根目录
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / env_file
    
    if env_path.exists():
        print(f"Loading config from {env_file}")
        load_dotenv(env_path)
    else:
        # Fallback to .env if specific file doesn't exist
        fallback_path = project_root / ".env"
        if fallback_path.exists():
            print("Loading config from .env")
            load_dotenv(fallback_path)
except ImportError:
    pass

# -----------------------------------------------------------------------------
# 1. 路径配置
# -----------------------------------------------------------------------------
# 辅助函数：安全获取路径环境变量
def get_path_env(key, default):
    val = os.getenv(key)
    if val:
        val = val.strip().strip('"').strip("'")
        # 如果在 Windows 上，且路径以 / 开头（典型的 Unix 绝对路径）
        # 且包含 /app 这种典型的 Docker 根目录，直接视为无效，强制回退
        if os.name == 'nt' and (val.startswith('/app') or val.startswith('/')):
             return default
        return val
    return default

# 优先使用环境变量 PROJECT_ROOT，否则回退到当前文件相对路径
_default_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROOT_DIR = get_path_env("PROJECT_ROOT", _default_root)

# 子目录配置 (支持环境变量覆盖)
MODELS_DIR = get_path_env("MODELS_DIR", os.path.join(ROOT_DIR, "checkpoints"))
DATA_DIR = get_path_env("DATA_DIR", os.path.join(ROOT_DIR, "data"))
FEATURES_DIR = get_path_env("FEATURES_DIR", os.path.join(DATA_DIR, "features"))
VOICEPRINTS_DIR = get_path_env("VOICEPRINTS_DIR", os.path.join(DATA_DIR, "voiceprints"))

# 默认模型路径
_default_model_name = "ecapa_mfcc_delta_best.pth"
DEFAULT_MODEL_PATH = get_path_env("DEFAULT_MODEL_PATH", os.path.join(MODELS_DIR, _default_model_name))
# DEFAULT_TEMPLATE_PATH is deprecated, removing default fallback
DEFAULT_TEMPLATE_PATH = get_path_env("DEFAULT_TEMPLATE_PATH", "")

# 兼容旧代码的别名
MODEL_PATH = DEFAULT_MODEL_PATH
# TEMPLATE_PATH is deprecated
TEMPLATE_PATH = DEFAULT_TEMPLATE_PATH

# -----------------------------------------------------------------------------
# 2. 音频与特征参数
# -----------------------------------------------------------------------------
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", 16000))
N_MFCC = int(os.getenv("N_MFCC", 13))
DEFAULT_N_MELS = int(os.getenv("DEFAULT_N_MELS", 40))
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", 192))

# 特征提取参数 (python_speech_features 默认值，显式定义以防变更)
WIN_LEN = 0.025
WIN_STEP = 0.01
N_FFT = 512

# 预加重系数
PRE_EMPHASIS_COEFF = 0.97

# -----------------------------------------------------------------------------
# 3. 推理与评估参数
# -----------------------------------------------------------------------------
DEFAULT_THRESHOLD = float(os.getenv("VOICE_VERIFY_THRESHOLD", 0.75))

# 自动检测设备 (优先使用环境变量，其次尝试 CUDA，最后回退到 CPU)
def _get_default_device():
    env_device = os.getenv("VOICE_ENGINE_DEVICE")
    if env_device:
        return env_device
    
    # 尝试导入 torch 检测 CUDA
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
        
    return "cpu"

DEFAULT_DEVICE = _get_default_device()


# -----------------------------------------------------------------------------
# 4. 特征类型定义
# -----------------------------------------------------------------------------
FEATURE_TYPE_MFCC = "mfcc"
FEATURE_TYPE_MFCC_DELTA = "mfcc_delta"
FEATURE_TYPE_LOGMEL = "logmel"

VALID_FEATURE_TYPES = [FEATURE_TYPE_MFCC, FEATURE_TYPE_MFCC_DELTA, FEATURE_TYPE_LOGMEL]


