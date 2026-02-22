# voice_engine/trainer.py
import time
import os
import math
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torch.utils.tensorboard import SummaryWriter
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_curve

from .dataset import SpeakerDataset, pad_collate
from .ecapa_tdnn import LightECAPA
from .losses import AAMSoftmaxLoss

# ==========================================
# Metrics Utilities (Merged from metrics.py)
# ==========================================

def _normalize_embeddings(embs):
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return embs / norms

def compute_pairs_scores(embs, labels, max_pairs=20000, seed=42, return_indices=False):
    """
    Sample positive and negative pairs from embeddings and compute cosine scores.
    """
    n = embs.shape[0]
    rng = np.random.RandomState(seed)
    same_scores = []
    diff_scores = []
    same_pairs = []
    diff_pairs = []
    
    # Create indices grouped by label
    idx_by_label = {}
    for i, l in enumerate(labels):
        idx_by_label.setdefault(l, []).append(i)
    labels_unique = list(idx_by_label.keys())

    # Sample same pairs
    attempts = 0
    target_count = max_pairs // 2
    while len(same_scores) < target_count and attempts < max_pairs * 5:
        spk = rng.choice(labels_unique)
        idxs = idx_by_label[spk]
        if len(idxs) < 2:
            attempts += 1
            continue
        i1, i2 = rng.choice(idxs, size=2, replace=False)
        s = np.dot(embs[i1], embs[i2]) / (np.linalg.norm(embs[i1]) * np.linalg.norm(embs[i2]) + 1e-9)
        same_scores.append(s)
        same_pairs.append((int(i1), int(i2)))
        attempts += 1

    # Sample diff pairs
    attempts = 0
    while len(diff_scores) < target_count and attempts < max_pairs * 5:
        spk1, spk2 = rng.choice(labels_unique, size=2, replace=False)
        i1 = rng.choice(idx_by_label[spk1])
        i2 = rng.choice(idx_by_label[spk2])
        s = np.dot(embs[i1], embs[i2]) / (np.linalg.norm(embs[i1]) * np.linalg.norm(embs[i2]) + 1e-9)
        diff_scores.append(s)
        diff_pairs.append((int(i1), int(i2)))
        attempts += 1

    y = np.hstack([np.ones(len(same_scores)), np.zeros(len(diff_scores))])
    scores = np.hstack([same_scores, diff_scores])
    if return_indices:
        pair_indices = same_pairs + diff_pairs
        return y, scores, np.array(same_scores), np.array(diff_scores), pair_indices
    return y, scores, np.array(same_scores), np.array(diff_scores)

def compute_cohort_stats(embs, labels, cohort_embs, cohort_labels, batch_size=256):
    if embs.size == 0 or cohort_embs.size == 0:
        return None, None
    embs = _normalize_embeddings(embs.astype(np.float32))
    cohort_embs = _normalize_embeddings(cohort_embs.astype(np.float32))
    cohort_labels = np.asarray(cohort_labels)
    n = embs.shape[0]
    mu = np.zeros(n, dtype=np.float32)
    sigma = np.zeros(n, dtype=np.float32)
    for start in range(0, n, batch_size):
        end = min(n, start + batch_size)
        batch = embs[start:end]
        scores = np.dot(batch, cohort_embs.T)
        batch_labels = labels[start:end]
        for i in range(scores.shape[0]):
            mask = cohort_labels != batch_labels[i]
            row = scores[i][mask]
            if row.size == 0:
                row = scores[i]
            mean = float(np.mean(row))
            std = float(np.std(row))
            if std < 1e-6:
                std = 1e-6
            mu[start + i] = mean
            sigma[start + i] = std
    return mu, sigma

def apply_score_norm(scores, pair_indices, mu, sigma, method="snorm"):
    if method not in {"znorm", "tnorm", "snorm"}:
        raise ValueError(f"Unsupported score_norm: {method}")
    scores = np.asarray(scores, dtype=np.float32)
    mu = np.asarray(mu, dtype=np.float32)
    sigma = np.asarray(sigma, dtype=np.float32)
    out = np.zeros_like(scores)
    for idx, (i, j) in enumerate(pair_indices):
        s = scores[idx]
        z = (s - mu[i]) / sigma[i]
        t = (s - mu[j]) / sigma[j]
        if method == "znorm":
            val = z
        elif method == "tnorm":
            val = t
        else:
            val = 0.5 * (z + t)
        
        # Sigmoid mapping to bring scores to (0, 1) range
        # Shift by +2.0 to make Z=2.0 (typical good match) map to 0.5
        # Scale by 2.0 to spread the distribution reasonably
        # 1 / (1 + exp(-(val - 2.0)))
        out[idx] = 1.0 / (1.0 + np.exp(-(val - 2.0)))
    return out

def compute_eer_from_embeddings(embs, labels, max_pairs=20000, seed=42):
    if embs is None or labels is None or len(embs) < 2:
        return None
    
    # Use compute_pairs_scores for consistent pair sampling
    y_true, y_scores, _, _ = compute_pairs_scores(embs, labels, max_pairs, seed)
    
    if len(y_true) == 0:
        return None
        
    fpr, tpr, thresholds = roc_curve(y_true, y_scores, pos_label=1)
    fnr = 1 - tpr
    idx = np.argmin(np.abs(fpr - fnr))
    eer = (fpr[idx] + fnr[idx]) / 2.0
    return float(eer)

def eer_from_roc(fpr, tpr, thresholds):
    """
    Calculate EER and the corresponding threshold from ROC curve data.
    """
    fnr = 1 - tpr
    abs_diffs = np.abs(fpr - fnr)
    idx = np.argmin(abs_diffs)
    eer = (fpr[idx] + fnr[idx]) / 2.0
    thr = thresholds[idx]
    return eer, thr

def compute_mindcf(fpr, tpr, thresholds, p_target=0.01, c_miss=1.0, c_fa=1.0):
    """
    Compute Minimum Decision Cost Function (MinDCF).
    """
    fnr = 1 - tpr
    dcf = c_miss * p_target * fnr + c_fa * (1 - p_target) * fpr
    idx = int(np.argmin(dcf))
    return {
        "min_dcf": float(dcf[idx]),
        "threshold": float(thresholds[idx]),
        "p_target": p_target,
        "c_miss": c_miss,
        "c_fa": c_fa,
        "dcf": [float(x) for x in dcf],
        "thresholds": [float(x) for x in thresholds],
    }

def recommend_threshold(fpr, tpr, thresholds):
    """
    Recommend threshold based on Youden's J statistic.
    """
    if len(fpr) == 0:
        return None, None
    youden = tpr - fpr
    idx = int(np.argmax(youden))
    return float(thresholds[idx]), float(youden[idx])

def compute_score_hist(same_scores, diff_scores, bins=30):
    """
    Compute score histogram bins for visualization.
    """
    all_scores = np.hstack([same_scores, diff_scores])
    if all_scores.size == 0:
        return {"bins": [], "same": [], "diff": []}
    min_v = float(np.min(all_scores))
    max_v = float(np.max(all_scores))
    if min_v == max_v:
        min_v -= 1e-3
        max_v += 1e-3
    edges = np.linspace(min_v, max_v, bins + 1)
    same_hist, _ = np.histogram(same_scores, bins=edges)
    diff_hist, _ = np.histogram(diff_scores, bins=edges)
    return {
        "bins": [float(v) for v in edges],
        "same": [int(v) for v in same_hist],
        "diff": [int(v) for v in diff_hist],
    }

def compute_calibration(scores, labels, bins=10):
    """
    Compute calibration curve metrics (ECE).
    """
    if len(scores) == 0:
        return {"bins": [], "accuracy": [], "confidence": [], "count": [], "ece": None}
    min_v = float(np.min(scores))
    max_v = float(np.max(scores))
    if min_v == max_v:
        min_v -= 1e-3
        max_v += 1e-3
    # Normalize scores to probability [0, 1] for ECE
    probs = (scores - min_v) / (max_v - min_v)
    probs = np.clip(probs, 0, 1)
    
    edges = np.linspace(0, 1, bins + 1)
    accuracy = []
    confidence = []
    counts = []
    ece = 0.0
    total = float(len(scores))
    
    for i in range(bins):
        left = edges[i]
        right = edges[i + 1]
        mask = (probs >= left) & (probs < right) if i < bins - 1 else (probs >= left) & (probs <= right)
        if not np.any(mask):
            accuracy.append(0.0)
            confidence.append((left + right) / 2.0)
            counts.append(0)
            continue
            
        bin_labels = labels[mask]
        bin_probs = probs[mask]
        
        acc = float(np.mean(bin_labels))
        conf = float(np.mean(bin_probs))
        count = int(np.sum(mask))
        
        accuracy.append(acc)
        confidence.append(conf)
        counts.append(count)
        ece += abs(acc - conf) * (count / total)
        
    return {
        "bins": [float(v) for v in edges],
        "accuracy": accuracy,
        "confidence": confidence,
        "count": counts,
        "ece": float(ece),
    }

# ==========================================
# Evaluation Utilities (Merged from evaluation.py)
# ==========================================

def extract_all_embeddings(model, device, feature_dir, batch_size=32, num_workers=0, mode='feature', augmentor=None):
    """
    Extract embeddings for an entire dataset directory.
    """
    ds = SpeakerDataset(feature_dir, mode=mode, augmentor=augmentor)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, collate_fn=pad_collate, num_workers=num_workers)
    
    model.eval()
    embs = []
    all_labels = []
    spk2idx = ds.spk2idx
    
    with torch.no_grad():
        for feats, lengths, lbs in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            embs.append(emb.cpu().numpy())
            all_labels.append(lbs.numpy())
            
    if not embs:
        return np.array([]), np.array([]), spk2idx
        
    embs = np.vstack(embs)
    all_labels = np.hstack(all_labels)
    return embs, all_labels, spk2idx

def build_templates(model, feature_dir, device, batch_size=32, max_speakers=0, max_utts_per_spk=0, seed=42):
    """
    Build user templates (mean embeddings) from a dataset.
    """
    ds = SpeakerDataset(feature_dir)
    spk2idx = ds.spk2idx
    
    # Filter speakers
    allowed_spk = None
    if max_speakers and max_speakers > 0 and len(spk2idx) > max_speakers:
        rng = np.random.RandomState(seed)
        all_spk = list(spk2idx.values())
        idx_sel = rng.choice(len(all_spk), size=max_speakers, replace=False)
        allowed_ids = set(all_spk[i] for i in idx_sel)
        allowed_spk = allowed_ids
        
    # Filter utterances per speaker
    use_limit_utt = max_utts_per_spk and max_utts_per_spk > 0
    utt_counter = {}
    indices = []
    
    for i, (_, label) in enumerate(ds.samples):
        if allowed_spk is not None and label not in allowed_spk:
            continue
        if use_limit_utt:
            cnt = utt_counter.get(label, 0)
            if cnt >= max_utts_per_spk:
                continue
            utt_counter[label] = cnt + 1
        indices.append(i)
    
    subset = Subset(ds, indices) if indices else ds
    loader = DataLoader(subset, batch_size=batch_size, shuffle=False, collate_fn=pad_collate)
    
    model.eval()
    emb_by_spk = {}
    
    with torch.no_grad():
        for feats, lengths, labels in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            emb = emb.cpu().numpy()
            labels = labels.numpy()
            
            for e, l in zip(emb, labels):
                if l not in emb_by_spk:
                    emb_by_spk[l] = []
                emb_by_spk[l].append(e)
                
    # Average
    templates = {}
    for l, embs_list in emb_by_spk.items():
        templates[l] = np.mean(embs_list, axis=0)
        
    return templates

# ==========================================
# Training Loop
# ==========================================

def train_epoch(model, loader, opt, device, loss_type, loss_fn):
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    for batch_idx, (feats, lengths, labels) in enumerate(loader):
        feats = feats.to(device)         # (B, C, T)
        lengths = lengths.to(device)
        labels = labels.to(device)
        opt.zero_grad()
        if loss_type == "aam":
            emb = model(feats, lengths, return_embedding=True)
            loss, logits = loss_fn(emb, labels, model.classifier.weight)
        else:
            logits, _ = model(feats, lengths)
            loss = loss_fn(logits, labels)
        loss.backward()
        opt.step()
        total_loss += loss.item()
        preds = torch.argmax(logits, dim=1)
        total_correct += (preds == labels).sum().item()
        total_count += labels.numel()
    avg_loss = total_loss / (batch_idx + 1)
    acc = total_correct / total_count if total_count else 0.0
    return avg_loss, acc

def evaluate(model, loader, device, loss_type, loss_fn):
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    with torch.no_grad():
        for batch_idx, (feats, lengths, labels) in enumerate(loader):
            feats = feats.to(device)
            lengths = lengths.to(device)
            labels = labels.to(device)
            if loss_type == "aam":
                emb = model(feats, lengths, return_embedding=True)
                loss, logits = loss_fn(emb, labels, model.classifier.weight)
            else:
                logits, _ = model(feats, lengths)
                loss = loss_fn(logits, labels)
            total_loss += loss.item()
            preds = torch.argmax(logits, dim=1)
            total_correct += (preds == labels).sum().item()
            total_count += labels.numel()
    avg_loss = total_loss / (batch_idx + 1)
    acc = total_correct / total_count if total_count else 0.0
    return avg_loss, acc

def collect_embeddings(model, loader, device):
    model.eval()
    all_embs = []
    all_labels = []
    with torch.no_grad():
        for feats, lengths, labels in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            all_embs.append(emb.cpu())
            all_labels.append(labels.cpu())
    if not all_embs:
        return None, None
    return torch.cat(all_embs, dim=0).numpy(), torch.cat(all_labels, dim=0).numpy()

class Trainer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = cfg.get("training", {}).get("device", "cuda" if torch.cuda.is_available() else "cpu")
        self.feature_dir = cfg.get("dataset", {}).get("feature_dir", "data/features")
        self.feature_type = cfg.get("dataset", {}).get("feature_type", "mfcc_delta")
        self.n_mels = cfg.get("dataset", {}).get("n_mels", 40)
        self.save_dir = cfg.get("paths", {}).get("save_dir", "models")
        self.log_dir = cfg.get("paths", {}).get("log_dir", "reports")
        self.tensorboard_dir = cfg.get("paths", {}).get("runs_dir", "runs")
        self.batch_size = cfg.get("training", {}).get("batch_size", 32)
        self.lr = cfg.get("training", {}).get("lr", 1e-3)
        self.epochs = cfg.get("training", {}).get("epochs", 40)
        self.loss_type = cfg.get("training", {}).get("loss", "ce")
        self.optimizer_type = cfg.get("training", {}).get("optimizer", "adam")
        self.loader_workers = cfg.get("dataset", {}).get("loader_workers", -1)
        self.early_stop = cfg.get("training", {}).get("early_stop", False)
        self.patience = cfg.get("training", {}).get("patience", 3)
        self.eer_interval = cfg.get("evaluation", {}).get("eer_interval", 5)
        self.eer_pairs = cfg.get("evaluation", {}).get("eer_pairs", 20000)
        
        self.model = None
        self.optimizer = None
        self.loss_fn = None
        self.train_loader = None
        self.val_loader = None
        
        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        self.writer = SummaryWriter(log_dir=self.tensorboard_dir)

    def setup(self):
        # Dataset
        augmentor = None
        if self.noise_dir and self.dataset_mode == 'raw':
            print(f"Enabling Noise Augmentation from {self.noise_dir}")
            from .dataset import NoiseAugmentor
            augmentor = NoiseAugmentor(self.noise_dir)

        # Auto-resolve feature directory based on feature_type
        # If data/features/logmel exists, use it instead of data/features
        dataset_root = self.feature_dir
        if self.dataset_mode == 'feature':
            potential_subdir = os.path.join(self.feature_dir, self.feature_type)
            if os.path.isdir(potential_subdir):
                print(f"Auto-detected feature subdirectory: {potential_subdir}")
                dataset_root = potential_subdir

        print(f"Loading dataset from {dataset_root} (mode={self.dataset_mode})...")
        ds = SpeakerDataset(
            dataset_root,
            mode=self.dataset_mode,
            augmentor=augmentor,
            feature_type=self.feature_type,
            n_mels=self.n_mels,
        )
        n_spk = len(ds.spk2idx)
        print(f"Found {len(ds)} utterances, {n_spk} speakers.")
        
        idxs = list(range(len(ds)))
        train_idx, val_idx = train_test_split(idxs, test_size=0.1, random_state=42)
        train_ds = Subset(ds, train_idx)
        val_ds = Subset(ds, val_idx)

        import os as _os, platform as _platform
        if self.loader_workers >= 0:
            num_workers = self.loader_workers
        else:
            if _platform.system() == "Windows":
                 num_workers = 0
            else:
                 num_workers = max(1, (_os.cpu_count() or 2) // 2)

        self.train_loader = DataLoader(train_ds, batch_size=self.batch_size, shuffle=True, collate_fn=pad_collate, num_workers=num_workers)
        self.val_loader = DataLoader(val_ds, batch_size=self.batch_size, shuffle=False, collate_fn=pad_collate, num_workers=num_workers)

        # Model
        sample_feat, _ = ds[0]
        feat_dim = int(sample_feat.shape[0])
        print(f"Feature dim: {feat_dim}")
        
        self.model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=n_spk).to(self.device)

        # Optimizer
        if self.optimizer_type == "adamw":
            self.optimizer = optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=1e-4)
        else:
            self.optimizer = optim.Adam(self.model.parameters(), lr=self.lr)

        # Loss
        if self.loss_type == "aam":
            self.loss_fn = AAMSoftmaxLoss().to(self.device)
        else:
            self.loss_fn = nn.CrossEntropyLoss().to(self.device)

    def run(self):
        self.setup()
        best_acc = 0.0
        patience_counter = 0
        
        for epoch in range(self.epochs):
            start = time.time()
            loss_train, acc_train = train_epoch(self.model, self.train_loader, self.optimizer, self.device, self.loss_type, self.loss_fn)
            loss_val, acc_val = evaluate(self.model, self.val_loader, self.device, self.loss_type, self.loss_fn)
            dur = time.time() - start
            
            print(f"Epoch {epoch+1}/{self.epochs} | T={dur:.1f}s | "
                  f"Train Loss={loss_train:.4f} Acc={acc_train:.4f} | "
                  f"Val Loss={loss_val:.4f} Acc={acc_val:.4f}")
            
            # TensorBoard logging
            self.writer.add_scalar("Loss/train", loss_train, epoch + 1)
            self.writer.add_scalar("Accuracy/train", acc_train, epoch + 1)
            self.writer.add_scalar("Loss/val", loss_val, epoch + 1)
            self.writer.add_scalar("Accuracy/val", acc_val, epoch + 1)
            
            # EER Check
            if (epoch + 1) % self.eer_interval == 0:
                print("Computing EER...")
                embs, labels = collect_embeddings(self.model, self.val_loader, self.device)
                eer = compute_eer_from_embeddings(embs, labels, max_pairs=self.eer_pairs)
                if eer is not None:
                    print(f"  => EER: {eer:.4f}")
                    self.writer.add_scalar("EER/val", eer, epoch + 1)

            # Checkpoint
            if acc_val > best_acc:
                best_acc = acc_val
                patience_counter = 0
                torch.save(self.model.state_dict(), os.path.join(self.save_dir, "ecapa_best.pth"))
                print("  => Saved best model.")
            else:
                patience_counter += 1
                if self.early_stop and patience_counter >= self.patience:
                    print("Early stopping.")
                    break
        
        # Save last
        torch.save(self.model.state_dict(), os.path.join(self.save_dir, "ecapa_last.pth"))
