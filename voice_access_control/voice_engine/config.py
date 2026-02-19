"""
Voice Engine Configuration
统一管理声纹识别引擎的全局配置参数，避免 Magic Numbers。
"""
import os

# -----------------------------------------------------------------------------
# 1. 路径配置
# -----------------------------------------------------------------------------
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_DIR = os.path.join(ROOT_DIR, "models")
DATA_DIR = os.path.join(ROOT_DIR, "data")
FEATURES_DIR = os.path.join(DATA_DIR, "features")
VOICEPRINTS_DIR = os.path.join(DATA_DIR, "voiceprints")

# 默认模型路径
DEFAULT_MODEL_PATH = os.path.join(MODELS_DIR, "ecapa_mfcc_delta_best.pth")
DEFAULT_TEMPLATE_PATH = os.path.join(VOICEPRINTS_DIR, "user_templates.npy")
MODEL_PATH = DEFAULT_MODEL_PATH
TEMPLATE_PATH = DEFAULT_TEMPLATE_PATH

# -----------------------------------------------------------------------------
# 2. 音频与特征参数
# -----------------------------------------------------------------------------
SAMPLE_RATE = 16000
N_MFCC = 13
DEFAULT_N_MELS = 40

# 特征提取参数 (python_speech_features 默认值，显式定义以防变更)
WIN_LEN = 0.025
WIN_STEP = 0.01
N_FFT = 512

# 预加重系数
PRE_EMPHASIS_COEFF = 0.97

# -----------------------------------------------------------------------------
# 3. 推理与评估参数
# -----------------------------------------------------------------------------
DEFAULT_THRESHOLD = 0.75
DEFAULT_DEVICE = "cuda"  # 自动检测逻辑在加载时处理，这里作为默认倾向

# -----------------------------------------------------------------------------
# 4. 特征类型定义
# -----------------------------------------------------------------------------
FEATURE_TYPE_MFCC = "mfcc"
FEATURE_TYPE_MFCC_DELTA = "mfcc_delta"
FEATURE_TYPE_LOGMEL = "logmel"

VALID_FEATURE_TYPES = [FEATURE_TYPE_MFCC, FEATURE_TYPE_MFCC_DELTA, FEATURE_TYPE_LOGMEL]
