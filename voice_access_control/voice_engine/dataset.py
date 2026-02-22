import os
import random
import glob
import numpy as np
import soundfile as sf
import scipy.signal
import torch
from torch.utils.data import Dataset
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
    VALID_FEATURE_TYPES,
    DEFAULT_N_MELS
)

# ==========================================
# Feature Extraction Utilities
# ==========================================

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

# ==========================================
# Augmentation Utilities
# ==========================================

def add_noise(y, snr_db, rng=None, noise_y=None):
    """
    Add noise to a signal at a specified SNR.
    """
    if snr_db is None:
        return y
        
    if rng is None:
        rng = np.random
        
    signal_power = np.mean(y ** 2)
    if signal_power <= 1e-12:
        return y
        
    snr_linear = 10 ** (snr_db / 10.0)
    noise_power = signal_power / snr_linear
    
    if noise_y is None:
        # White noise
        noise = rng.normal(0.0, np.sqrt(noise_power), size=y.shape)
        return y + noise
        
    # Real noise logic
    if len(noise_y) < len(y):
        rep = int(np.ceil(len(y) / len(noise_y)))
        src = np.tile(noise_y, rep)[: len(y)]
    else:
        start = rng.randint(0, len(noise_y) - len(y) + 1)
        src = noise_y[start : start + len(y)]
    
    src_power = np.mean(src ** 2)
    if src_power > 1e-12:
        src = src / np.sqrt(src_power)  # Normalize to unit power
    
    noise = src * np.sqrt(noise_power)
    
    return y + noise

class NoiseAugmentor:
    def __init__(self, noise_dir, snr_min=0, snr_max=15, sample_rate=16000):
        self.noise_dir = noise_dir
        self.snr_min = snr_min
        self.snr_max = snr_max
        self.sample_rate = sample_rate
        self.noises = []
        self._load_noises()

    def _load_noises(self):
        if not os.path.exists(self.noise_dir):
            print(f"Warning: Noise dir {self.noise_dir} not found.")
            return
            
        files = glob.glob(os.path.join(self.noise_dir, "*.wav"))
        print(f"Loading {len(files)} noise files from {self.noise_dir}...")
        for f in files:
            try:
                y, sr = sf.read(f)
                if y.ndim > 1:
                    y = y.mean(axis=1) # mix to mono
                if sr != self.sample_rate:
                    import scipy.signal
                    num = int(len(y) * self.sample_rate / sr)
                    y = scipy.signal.resample(y, num)
                self.noises.append(y)
            except Exception as e:
                print(f"Error loading {f}: {e}")
        print(f"Loaded {len(self.noises)} valid noise clips.")

    def __call__(self, wav):
        if not self.noises:
            return wav
            
        # 80% chance to keep clean? Or 20%? 
        # Previous code said: "if random.random() > 0.8: return wav" -> 20% chance to augment?
        # Wait, if > 0.8 return wav -> 80% chance to augment if random is 0..0.8? No.
        # random() returns [0, 1). > 0.8 happens 20% of the time.
        # So 20% clean, 80% augmented.
        if random.random() > 0.8:
            return wav

        noise_idx = random.randint(0, len(self.noises) - 1)
        noise = self.noises[noise_idx]
        snr = random.uniform(self.snr_min, self.snr_max)
        
        return add_noise(wav, snr, noise_y=noise)

# ==========================================
# Dataset
# ==========================================

class SpeakerDataset(Dataset):
    """
    mode='feature': load .npy features from feature_root (default)
    mode='raw': load .wav files from feature_root (which should be data/processed), apply augmentation, extract features
    """
    def __init__(self, feature_root, mode='feature', augmentor=None, limit=None, feature_type=None, n_mels=None):
        self.feature_root = feature_root
        self.mode = mode
        self.augmentor = augmentor
        self.feature_type = feature_type or FEATURE_TYPE_MFCC_DELTA
        self.n_mels = n_mels or DEFAULT_N_MELS
        self.samples = []   # list of (path, label)
        self.spk2idx = {}
        
        if not os.path.exists(feature_root):
            print(f"Warning: {feature_root} does not exist.")
            return

        speakers = sorted([d for d in os.listdir(feature_root) if os.path.isdir(os.path.join(feature_root, d))])
        for idx, spk in enumerate(speakers):
            self.spk2idx[spk] = idx
            spk_dir = os.path.join(feature_root, spk)
            for fn in os.listdir(spk_dir):
                if self.mode == 'feature' and fn.endswith(".npy"):
                    self.samples.append((os.path.join(spk_dir, fn), idx))
                elif self.mode == 'raw' and fn.endswith(".wav"):
                    self.samples.append((os.path.join(spk_dir, fn), idx))
        
        if limit:
            self.samples = self.samples[:limit]
            
        print(f"Loaded {len(self.samples)} samples, {len(self.spk2idx)} speakers. Mode={self.mode}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        
        if self.mode == 'feature':
            feat = np.load(path)            # (T, feat_dim)
        else:
            # Raw wav mode
            try:
                y, sr = load_and_resample(path)
                if self.augmentor:
                    y = self.augmentor(y)
                
                feat = extract_feature_from_signal(y, sr, feature_type=self.feature_type, n_mels=self.n_mels)
            except Exception as e:
                print(f"Error processing {path}: {e}")
                feat = np.zeros((100, 39), dtype=np.float32)

        feat = torch.from_numpy(feat).float().transpose(0, 1)  # -> (feat_dim, T)
        return feat, torch.tensor(label, dtype=torch.long)

def pad_collate(batch, pad_value=0.0):
    """
    batch: list of (feat, label), feat is (C, T_i)
    return: feats_padded (B, C, T_max), lengths (B,), labels (B,)
    """
    feats, labels = zip(*batch)
    lengths = [f.shape[1] for f in feats]
    C = feats[0].shape[0]
    T_max = max(lengths)
    B = len(feats)
    out = feats[0].new_full((B, C, T_max), pad_value)
    for i, f in enumerate(feats):
        out[i, :, :f.shape[1]] = f
    return out, torch.tensor(lengths, dtype=torch.long), torch.stack(labels)
