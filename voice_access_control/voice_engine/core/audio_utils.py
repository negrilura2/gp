import numpy as np
import soundfile as sf
import scipy.signal

from ..config import (
    SAMPLE_RATE,
    N_MFCC,
    WIN_LEN,
    WIN_STEP,
    N_FFT,
    PRE_EMPHASIS_COEFF,
    FEATURE_TYPE_MFCC_DELTA,
    FEATURE_TYPE_LOGMEL,
    VALID_FEATURE_TYPES,
    DEFAULT_N_MELS
)

def load_and_resample(wav_path):
    """
    加载并重采样音频。
    """
    try:
        y, sr = sf.read(wav_path)
    except Exception as e:
        raise RuntimeError(f"无法读取音频文件 {wav_path}: {e}")

    if len(y) == 0:
        raise RuntimeError(f"音频文件为空: {wav_path}")

    # 转单声道
    if y.ndim > 1:
        y = y.mean(axis=1)

    # 重采样
    if sr != SAMPLE_RATE:
        try:
            num = int(len(y) * SAMPLE_RATE / sr)
            y = scipy.signal.resample(y, num)
            sr = SAMPLE_RATE
        except Exception as e:
            print(f"ERROR: Resample failed: {e}")
            raise
    
    return y, sr

def pre_emphasis(y, coeff=PRE_EMPHASIS_COEFF):
    return np.append(y[0], y[1:] - coeff * y[:-1])

def normalize_signal(y):
    max_val = np.max(np.abs(y))
    if max_val < 1e-6:
        return y
    return y / max_val

def get_feature_dim(feature_type, n_mels=DEFAULT_N_MELS):
    if feature_type == FEATURE_TYPE_MFCC_DELTA:
        return N_MFCC * 3
    if feature_type == FEATURE_TYPE_LOGMEL:
        return n_mels
    return N_MFCC * 3

def infer_feature_type_from_feat_dim(feat_dim, n_mels=DEFAULT_N_MELS):
    if feat_dim == N_MFCC * 3:
        return FEATURE_TYPE_MFCC_DELTA
    if feat_dim == n_mels:
        return FEATURE_TYPE_LOGMEL
    return FEATURE_TYPE_MFCC_DELTA

def extract_feature_from_signal(y, sr, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=DEFAULT_N_MELS, normalize=False):
    # Use python_speech_features or librosa. 
    # For now assume python_speech_features is installed as per original code.
    from python_speech_features import mfcc, delta, logfbank
    
    if normalize:
        y = normalize_signal(y)

    if feature_type == FEATURE_TYPE_LOGMEL:
        try:
            feat = logfbank(
                y,
                samplerate=sr,
                nfilt=n_mels,
                winlen=WIN_LEN,
                winstep=WIN_STEP,
                nfft=N_FFT,
            )
        except Exception as e:
            raise RuntimeError(f"LogMel extraction failed: {e}")
    elif feature_type == FEATURE_TYPE_MFCC_DELTA: 
        m = mfcc(
            y, 
            samplerate=sr, 
            numcep=N_MFCC, 
            winlen=WIN_LEN, 
            winstep=WIN_STEP, 
            nfft=N_FFT
        )
        d1 = delta(m, 2)
        d2 = delta(d1, 2)
        feat = np.hstack([m, d1, d2])
    else:
        raise ValueError(f"Unknown feature type: {feature_type}")

    return feat

def extract_feature_numpy(wav_path, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=DEFAULT_N_MELS, normalize=False):
    if feature_type not in VALID_FEATURE_TYPES:
        raise ValueError(f"不支持的特征类型: {feature_type}")
    y, sr = load_and_resample(wav_path)
    return extract_feature_from_signal(y, sr, feature_type, n_mels, normalize)
