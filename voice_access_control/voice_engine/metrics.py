import numpy as np

def _normalize_embeddings(embs):
    norms = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    return embs / norms

def compute_pairs_scores(embs, labels, max_pairs=20000, seed=42, return_indices=False):
    """
    Sample positive and negative pairs from embeddings and compute cosine scores.
    
    Args:
        embs (np.ndarray): Embeddings (N, dim).
        labels (np.ndarray): Labels (N,).
        max_pairs (int): Maximum number of pairs to sample.
        seed (int): Random seed.
        
    Returns:
        tuple: (y_true, y_scores, same_scores, diff_scores[, pair_indices])
            y_true: 1 for same, 0 for diff
            y_scores: cosine similarities
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
    # Note: Cosine similarity is usually [-1, 1], but for verification we often map it.
    # Here we just min-max normalize for calibration plot purpose.
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
