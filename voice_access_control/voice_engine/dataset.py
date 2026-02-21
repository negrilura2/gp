import os
import numpy as np
import torch
from torch.utils.data import Dataset
import soundfile as sf
from .features import extract_feature_from_signal, load_and_resample
from .config import FEATURE_TYPE_MFCC_DELTA, DEFAULT_N_MELS

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
            # 1. Load wav
            # 2. Augment
            # 3. Extract features
            try:
                y, sr = load_and_resample(path)
                if self.augmentor:
                    y = self.augmentor(y)
                
                # Extract features (T, feat_dim)
                # Note: extract_feature_from_signal returns (T, D) usually? 
                # Let's check features.py. It returns (T, D).
                # But existing code does .transpose(0, 1) to get (D, T).
                feat = extract_feature_from_signal(y, sr, feature_type=self.feature_type, n_mels=self.n_mels)
            except Exception as e:
                print(f"Error processing {path}: {e}")
                # return a dummy feature or zero?
                # For robustness, maybe load another sample?
                # For now, return zeros of typical shape (100, 39)
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
