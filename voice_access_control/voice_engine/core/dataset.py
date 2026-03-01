import os
import random
import glob
import numpy as np
import soundfile as sf
import scipy.signal
import torch
from torch.utils.data import Dataset
from pathlib import Path

from ..config import (
    FEATURE_TYPE_MFCC_DELTA,
    DEFAULT_N_MELS,
    SAMPLE_RATE
)

# Import shared audio utilities to avoid code duplication
from .audio_utils import (
    load_and_resample,
    pre_emphasis,
    normalize_signal,
    get_feature_dim,
    infer_feature_type_from_feat_dim,
    extract_feature_from_signal,
    extract_feature_numpy,
)

# ==========================================
# Feature Extraction Utilities (Tensor)
# ==========================================

def extract_feature_tensor(wav_path, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=DEFAULT_N_MELS, device="cpu"):
    """
    封装 extract_feature_numpy，返回模型可用的 Tensor。
    """
    feat = extract_feature_numpy(wav_path, feature_type, n_mels, normalize=False)
    tensor = torch.from_numpy(feat.T).unsqueeze(0).float().to(device)
    return tensor

# ==========================================
# Augmentation Utilities
# ==========================================

def add_noise(y, snr_db, rng=None, noise_y=None):
    if snr_db is None: return y
    if rng is None: rng = np.random
    signal_power = np.mean(y ** 2)
    if signal_power <= 1e-12: return y
    snr_linear = 10 ** (snr_db / 10.0)
    noise_power = signal_power / snr_linear
    if noise_y is None:
        noise = rng.normal(0.0, np.sqrt(noise_power), size=y.shape)
        return y + noise
    if len(noise_y) < len(y):
        rep = int(np.ceil(len(y) / len(noise_y)))
        src = np.tile(noise_y, rep)[: len(y)]
    else:
        start = rng.randint(0, len(noise_y) - len(y) + 1)
        src = noise_y[start : start + len(y)]
    src_power = np.mean(src ** 2)
    if src_power > 1e-12:
        src = src / np.sqrt(src_power)
    noise = src * np.sqrt(noise_power)
    return y + noise

def spec_augment(feat, T=40, F=15, time_mask_num=2, freq_mask_num=2):
    feat = feat.copy()
    tau, v = feat.shape
    # Calculate mean value to use for masking instead of 0
    # This is crucial for Log-Mel features which are often negative (dB scale)
    # Masking with 0 would be equivalent to adding loud noise!
    mask_val = feat.mean() 
    
    for _ in range(time_mask_num):
        t = np.random.randint(0, T + 1)
        if tau - t <= 0: continue
        t0 = np.random.randint(0, tau - t)
        feat[t0:t0+t, :] = mask_val
    for _ in range(freq_mask_num):
        f = np.random.randint(0, F + 1)
        if v - f <= 0: continue
        f0 = np.random.randint(0, v - f)
        feat[:, f0:f0+f] = mask_val
    return feat

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
            return
        files = glob.glob(os.path.join(self.noise_dir, "*.wav"))
        for f in files:
            try:
                y, sr = sf.read(f)
                if y.ndim > 1: y = y.mean(axis=1)
                if sr != self.sample_rate:
                    import scipy.signal
                    num = int(len(y) * self.sample_rate / sr)
                    y = scipy.signal.resample(y, num)
                self.noises.append(y)
            except Exception: pass

    def __call__(self, wav):
        if not self.noises: return wav
        if random.random() > 0.8: return wav
        noise_idx = random.randint(0, len(self.noises) - 1)
        noise = self.noises[noise_idx]
        snr = random.uniform(self.snr_min, self.snr_max)
        return add_noise(wav, snr, noise_y=noise)

# ==========================================
# Dataset
# ==========================================

def pad_collate(batch):
    """
    Collate function to pad variable length features/wavs.
    Returns: (feats, lengths, labels)
    feats: (B, C, T) or (B, T) depending on mode
    """
    # Batch is list of (feat, label)
    # feat is (T, dim) for feature mode, or (T,) for raw mode
    
    # Sort by length (descending) for packing (optional but good practice)
    batch.sort(key=lambda x: x[0].shape[0], reverse=True)
    
    feats, labels = zip(*batch)
    lengths = [x.shape[0] for x in feats]
    max_len = max(lengths)
    
    # Pad
    padded_feats = []
    for f in feats:
        # f: (T, D) or (T,)
        pad_len = max_len - f.shape[0]
        if f.ndim == 2:
            # Feature mode: (T, D) -> Pad T dimension
            # np.pad expects ((before_1, after_1), (before_2, after_2))
            padded = np.pad(f, ((0, pad_len), (0, 0)), mode='constant')
        else:
            # Raw mode: (T,)
            padded = np.pad(f, (0, pad_len), mode='constant')
        padded_feats.append(padded)
        
    padded_feats = np.array(padded_feats) # (B, T, D) or (B, T)
    
    # Convert to Tensor
    feats_tensor = torch.from_numpy(padded_feats).float()
    labels_tensor = torch.LongTensor(labels)
    lengths_tensor = torch.LongTensor(lengths)
    
    if feats_tensor.ndim == 3:
        # (B, T, D) -> (B, D, T) for Conv1d
        feats_tensor = feats_tensor.permute(0, 2, 1)
    
    return feats_tensor, lengths_tensor, labels_tensor

class SpeakerDataset(Dataset):
    def __init__(self, feature_root, mode='feature', augmentor=None, limit=None, feature_type=None, n_mels=None, class_mapping=None, spec_augment=False):
        self.feature_root = Path(feature_root)
        self.mode = mode
        self.augmentor = augmentor
        self.spec_augment = spec_augment
        self.feature_type = feature_type or FEATURE_TYPE_MFCC_DELTA
        self.n_mels = n_mels or DEFAULT_N_MELS
        self.samples = []   # list of (path, label)
        self.spk2idx = {}
        
        if not self.feature_root.exists():
            print(f"Warning: {feature_root} does not exist.")
            return

        # Improved file discovery: Recursive
        ext = ".npy" if mode == 'feature' else ".wav"
        
        # Strategy:
        # 1. Find all files recursively.
        # 2. Extract speaker ID from parent folder name.
        #    Assumes structure: root/.../speaker_id/file.ext
        #    If structure is flat (root/file.ext), extracts from filename (id1001-...).
        
        files = sorted(list(self.feature_root.rglob(f"*{ext}")))
        
        if not files:
            print(f"No {ext} files found in {feature_root}")
            return
            
        # Parse speakers
        # We need to build a mapping.
        # If class_mapping is provided, we use it and filter.
        # If not, we build it.
        
        found_samples = [] # (path, spk_id)
        
        for f in files:
            # Heuristic for speaker ID
            # Check if parent is the speaker ID
            # We assume the directory structure is meaningful if it's not the root.
            if f.parent != self.feature_root:
                # Use parent folder name as speaker ID
                # Exception: if parent is 'train' or 'valid' or 'test', then it's flat inside split?
                # No, we established structure is split/speaker/file.
                # So if f is root/train/spk01/file.wav -> parent is spk01.
                # If f is root/spk01/file.wav -> parent is spk01.
                spk_id = f.parent.name
            else:
                # Flat structure in root
                # Parse from filename
                if f.name.startswith("id") and "-" in f.name:
                    spk_id = f.name.split("-")[0]
                else:
                    # Fallback: unknown
                    spk_id = "unknown"
            
            found_samples.append((str(f), spk_id))
            
        # Build or use mapping
        unique_spks = sorted(list(set(s[1] for s in found_samples)))
        
        if class_mapping is not None:
            self.spk2idx = class_mapping
            # We do NOT add new speakers.
        else:
            self.spk2idx = {spk: idx for idx, spk in enumerate(unique_spks)}
            
        # Filter and create final sample list
        skipped_count = 0
        for path, spk in found_samples:
            if spk in self.spk2idx:
                self.samples.append((path, self.spk2idx[spk]))
            else:
                # Open Set Validation Support:
                # If we are validating and encounter a new speaker, we usually skip for Classification Loss.
                # But for EER, we need it.
                # If class_mapping was provided, it implies we are restricted to that set (Closed Set).
                # To support Open Set, the caller should NOT provide class_mapping, or we should have a flag.
                # Current behavior: Skip.
                skipped_count += 1
                
        if limit:
            self.samples = self.samples[:limit]
            
        print(f"Loaded {len(self.samples)} samples from {len(unique_spks)} speakers found. (Skipped {skipped_count}). Mode={self.mode}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        
        if self.mode == 'feature':
            feat = np.load(path)
            if self.spec_augment:
                feat = spec_augment(feat)
        else:
            try:
                y, sr = load_and_resample(path)
                if self.augmentor:
                    y = self.augmentor(y)
                feat = extract_feature_from_signal(y, sr, feature_type=self.feature_type, n_mels=self.n_mels)
                if self.spec_augment:
                    feat = spec_augment(feat)
            except Exception as e:
                print(f"Error loading {path}: {e}")
                # Return zero feature
                dim = get_feature_dim(self.feature_type, self.n_mels)
                feat = np.zeros((200, dim), dtype=np.float32)

        return feat, label
