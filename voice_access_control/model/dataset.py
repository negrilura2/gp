# model/dataset.py
import os
import numpy as np
import torch
from torch.utils.data import Dataset

class SpeakerDataset(Dataset):
    """
    从 data/features 读取 .npy 特征，每个文件 (T, feat_dim)
    返回 feature (feat_dim, T) 和 label (int)
    """
    def __init__(self, feature_root):
        self.samples = []   # list of (path, label)
        self.spk2idx = {}
        speakers = sorted([d for d in os.listdir(feature_root) if os.path.isdir(os.path.join(feature_root, d))])
        for idx, spk in enumerate(speakers):
            self.spk2idx[spk] = idx
            spk_dir = os.path.join(feature_root, spk)
            for fn in os.listdir(spk_dir):
                if fn.endswith(".npy"):
                    self.samples.append((os.path.join(spk_dir, fn), idx))
        print(f"Loaded {len(self.samples)} samples, {len(self.spk2idx)} speakers")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        feat = np.load(path)            # (T, feat_dim)
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
