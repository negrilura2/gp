"""
Feature Extraction Module
提供统一的特征提取逻辑，供训练、注册、验证、测试所有脚本调用。
强制统一：Load -> Resample -> Pre-emphasis -> Normalize (Optional) -> Extract -> Transpose
"""
import os
import numpy as np
import soundfile as sf
import scipy.signal
import torch
import librosa
from python_speech_features import mfcc, delta, logfbank

from .config import (
    SAMPLE_RATE,
    N_MFCC,
    WIN_LEN,
    WIN_STEP,
    N_FFT,
    PRE_EMPHASIS_COEFF,
    FEATURE_TYPE_MFCC,
    FEATURE_TYPE_MFCC_DELTA,
    FEATURE_TYPE_LOGMEL,
    VALID_FEATURE_TYPES
)

def load_and_resample(wav_path):
    """
    加载并重采样音频。
    1. 读取文件
    2. 转单声道
    3. 重采样到 SAMPLE_RATE (使用 scipy.signal.resample 以避免 librosa hang)
    """
    try:
        y, sr = sf.read(wav_path)
    except Exception as e:
        # Fallback to librosa if sf fails? But sf is robust.
        # Just re-raise with path info
        raise RuntimeError(f"无法读取音频文件 {wav_path}: {e}")

    if len(y) == 0:
        raise RuntimeError(f"音频文件为空: {wav_path}")

    # 转单声道
    if y.ndim > 1:
        y = y.mean(axis=1)

    # 重采样
    if sr != SAMPLE_RATE:
        # print(f"DEBUG: Resampling {sr}->{SAMPLE_RATE} for {wav_path}")
        try:
            num = int(len(y) * SAMPLE_RATE / sr)
            y = scipy.signal.resample(y, num)
            sr = SAMPLE_RATE
        except Exception as e:
            print(f"ERROR: Resample failed: {e}")
            raise
    
    return y, sr

def pre_emphasis(y, coeff=PRE_EMPHASIS_COEFF):
    """
    预加重滤波器。
    y[n] = x[n] - coeff * x[n-1]
    """
    return np.append(y[0], y[1:] - coeff * y[:-1])

def normalize_signal(y):
    """
    信号幅值归一化。
    """
    max_val = np.max(np.abs(y))
    if max_val < 1e-6:
        return y
    return y / max_val

def get_feature_dim(feature_type, n_mels=40):
    """
    根据特征类型返回维度。
    """
    if feature_type == FEATURE_TYPE_MFCC:
        return N_MFCC
    if feature_type == FEATURE_TYPE_LOGMEL:
        return n_mels
    return N_MFCC * 3  # mfcc_delta

def extract_feature_from_signal(y, sr, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=40, normalize=False):
    """
    从信号提取特征 (numpy array)。
    参数:
        y: 信号 (单声道)
        sr: 采样率
    """
    # Pre-emphasis
    # y = pre_emphasis(y) 

    # Normalize
    if normalize:
        y = normalize_signal(y)

    # Extract
    if feature_type == FEATURE_TYPE_LOGMEL:
        # LogMel
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
            
    elif feature_type == FEATURE_TYPE_MFCC:
        # MFCC
        feat = mfcc(
            y, 
            samplerate=sr, 
            numcep=N_MFCC, 
            winlen=WIN_LEN, 
            winstep=WIN_STEP, 
            nfft=N_FFT
        )
        
    else: 
        # MFCC Delta
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

    return feat

def extract_feature_numpy(wav_path, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=40, normalize=False):
    """
    核心特征提取函数。返回 numpy array (T, dim)。
    
    参数:
        wav_path: 音频路径
        feature_type: mfcc | mfcc_delta | logmel
        n_mels: LogMel 频带数 (仅对 logmel 有效)
        normalize: 是否对时域信号进行幅值归一化 (LogMel 训练时未归一化，MFCC 默认也未归一化)
                   建议保持 False 以对齐训练代码。
    """
    if feature_type not in VALID_FEATURE_TYPES:
        raise ValueError(f"不支持的特征类型: {feature_type}")

    # 1. Load & Resample
    y, sr = load_and_resample(wav_path)

    return extract_feature_from_signal(y, sr, feature_type, n_mels, normalize)

def extract_feature_tensor(wav_path, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=40, device="cpu"):
    """
    封装 extract_feature_numpy，返回模型可用的 Tensor。
    
    返回:
        tensor: (1, dim, T)  <-- 注意这里已经完成了转置和升维，可以直接送入模型
    """
    feat = extract_feature_numpy(wav_path, feature_type, n_mels, normalize=False)
    
    # feat is (T, dim)
    # Model expects (B, C, T) -> (1, dim, T)
    
    tensor = torch.from_numpy(feat.T).unsqueeze(0).float().to(device)
    return tensor

def infer_feature_type_from_feat_dim(feat_dim, n_mels=40):
    """
    从特征维度反推类型 (用于加载模型时猜测)。
    """
    if feat_dim == N_MFCC:
        return FEATURE_TYPE_MFCC
    if feat_dim == N_MFCC * 3:
        return FEATURE_TYPE_MFCC_DELTA
    if feat_dim == n_mels:
        return FEATURE_TYPE_LOGMEL
    # Fallback default
    return FEATURE_TYPE_MFCC_DELTA
