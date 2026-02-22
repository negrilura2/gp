import numpy as np
from sklearn.metrics import roc_curve
import torch
from torch.utils.data import DataLoader, Subset
from .dataset import SpeakerDataset, pad_collate


def normalize_embeddings(embs):
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return embs / norms


def compute_pairs_scores(embs, labels, max_pairs=20000, seed=42, return_indices=False):
    n = embs.shape[0]
    rng = np.random.RandomState(seed)
    same_scores = []
    diff_scores = []
    same_pairs = []
    diff_pairs = []

    idx_by_label = {}
    for i, l in enumerate(labels):
        idx_by_label.setdefault(l, []).append(i)
    labels_unique = list(idx_by_label.keys())

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
    embs = normalize_embeddings(embs.astype(np.float32))
    cohort_embs = normalize_embeddings(cohort_embs.astype(np.float32))
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
        out[idx] = 1.0 / (1.0 + np.exp(-(val - 2.0)))
    return out


def compute_eer_from_embeddings(embs, labels, max_pairs=20000, seed=42):
    if embs is None or labels is None or len(embs) < 2:
        return None
    y_true, y_scores, _, _ = compute_pairs_scores(embs, labels, max_pairs, seed)
    if len(y_true) == 0:
        return None
    fpr, tpr, thresholds = roc_curve(y_true, y_scores, pos_label=1)
    fnr = 1 - tpr
    idx = np.argmin(np.abs(fpr - fnr))
    eer = (fpr[idx] + fnr[idx]) / 2.0
    return float(eer)


def eer_from_roc(fpr, tpr, thresholds):
    fnr = 1 - tpr
    abs_diffs = np.abs(fpr - fnr)
    idx = np.argmin(abs_diffs)
    eer = (fpr[idx] + fnr[idx]) / 2.0
    thr = thresholds[idx]
    return eer, thr


def compute_mindcf(fpr, tpr, thresholds, p_target=0.01, c_miss=1.0, c_fa=1.0):
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
    if len(fpr) == 0:
        return None, None
    youden = tpr - fpr
    idx = int(np.argmax(youden))
    return float(thresholds[idx]), float(youden[idx])


def compute_score_hist(same_scores, diff_scores, bins=30):
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
    if len(scores) == 0:
        return {"bins": [], "accuracy": [], "confidence": [], "count": [], "ece": None}
    min_v = float(np.min(scores))
    max_v = float(np.max(scores))
    if min_v == max_v:
        min_v -= 1e-3
        max_v += 1e-3
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
        if i < bins - 1:
            mask = (probs >= left) & (probs < right)
        else:
            mask = (probs >= left) & (probs <= right)
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


def extract_all_embeddings(model, device, feature_dir, batch_size=32, num_workers=0, mode="feature", augmentor=None):
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
    ds = SpeakerDataset(feature_dir)
    spk2idx = ds.spk2idx
    allowed_spk = None
    if max_speakers and max_speakers > 0 and len(spk2idx) > max_speakers:
        rng = np.random.RandomState(seed)
        all_spk = list(spk2idx.values())
        idx_sel = rng.choice(len(all_spk), size=max_speakers, replace=False)
        allowed_ids = set(all_spk[i] for i in idx_sel)
        allowed_spk = allowed_ids
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
    templates = {}
    for l, embs_list in emb_by_spk.items():
        templates[l] = np.mean(embs_list, axis=0)
    return templates


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
