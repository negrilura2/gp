# scripts/eval/eval_threshold.py
"""
Usage:
python -m scripts.eval.eval_threshold --model models/ecapa_best.pth --feature_dir data/features --out_dir reports --max_pairs 20000

Outputs:
reports/roc.png
reports/eer_threshold.json  ({"eer":..., "threshold":...})
"""
import os
import sys
import json
import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import FEATURES_DIR, MODELS_DIR, REPORTS_DIR

from voice_engine.ecapa_tdnn import LightECAPA
from voice_engine.dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader

def extract_all_embeddings(model, device, feature_dir, batch_size=32, num_workers=2):
    ds = SpeakerDataset(feature_dir)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, collate_fn=pad_collate, num_workers=num_workers)
    model.eval()
    embs = []
    labels = []
    with torch.no_grad():
        for feats, lengths, lbs in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)  # (B, emb_dim)
            embs.append(emb.cpu().numpy())
            labels.append(lbs.numpy())
    embs = np.vstack(embs)
    labels = np.hstack(labels)
    return embs, labels, ds.spk2idx

def compute_pairs_scores(embs, labels, max_pairs=20000):
    # sample pairs for same and different
    n = embs.shape[0]
    rng = np.random.RandomState(42)
    same_scores = []
    diff_scores = []
    # create indices grouped by label
    idx_by_label = {}
    for i, l in enumerate(labels):
        idx_by_label.setdefault(l, []).append(i)
    labels_unique = list(idx_by_label.keys())

    # sample same pairs
    attempts = 0
    while len(same_scores) < max_pairs//2 and attempts < max_pairs*5:
        spk = rng.choice(labels_unique)
        idxs = idx_by_label[spk]
        if len(idxs) < 2:
            attempts += 1
            continue
        i1, i2 = rng.choice(idxs, size=2, replace=False)
        s = np.dot(embs[i1], embs[i2]) / (np.linalg.norm(embs[i1]) * np.linalg.norm(embs[i2]) + 1e-9)
        same_scores.append(s)
        attempts += 1

    # sample diff pairs
    attempts = 0
    while len(diff_scores) < max_pairs//2 and attempts < max_pairs*5:
        spk1, spk2 = rng.choice(labels_unique, size=2, replace=False)
        i1 = rng.choice(idx_by_label[spk1])
        i2 = rng.choice(idx_by_label[spk2])
        s = np.dot(embs[i1], embs[i2]) / (np.linalg.norm(embs[i1]) * np.linalg.norm(embs[i2]) + 1e-9)
        diff_scores.append(s)
        attempts += 1

    y = np.hstack([np.ones(len(same_scores)), np.zeros(len(diff_scores))])  # 1: same, 0: diff
    scores = np.hstack([same_scores, diff_scores])
    return y, scores, np.array(same_scores), np.array(diff_scores)

def eer_from_roc(fpr, tpr, thresholds):
    # fnr = 1 - tpr
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
        "p_target": float(p_target),
        "c_miss": float(c_miss),
        "c_fa": float(c_fa),
        "threshold": float(thresholds[idx]),
        "min_dcf": float(dcf[idx]),
        "dcf": [float(v) for v in dcf],
        "thresholds": [float(v) for v in thresholds],
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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.path.join(MODELS_DIR, "ecapa_best.pth"))
    parser.add_argument("--feature_dir", default=str(FEATURES_DIR))
    parser.add_argument("--out_dir", default=str(REPORTS_DIR))
    parser.add_argument("--max_pairs", type=int, default=20000)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    backend_dir = os.path.join(args.out_dir, "archive", "backend_responses")
    roc_dir = os.path.join(args.out_dir, "archive", "plots", "roc")
    os.makedirs(backend_dir, exist_ok=True)
    os.makedirs(roc_dir, exist_ok=True)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"

    ds_tmp = SpeakerDataset(args.feature_dir)
    if len(ds_tmp) == 0:
        raise ValueError("feature_dir 内没有可用特征文件")
    sample_feat, _ = ds_tmp[0]
    feat_dim_data = int(sample_feat.shape[0])

    print("加载模型...")
    state = torch.load(args.model, map_location=device)
    ckpt_feat_dim = None
    w = state.get("layer1.conv.weight")
    if w is not None:
        ckpt_feat_dim = int(w.shape[1])
    if ckpt_feat_dim is not None and ckpt_feat_dim != feat_dim_data:
        raise RuntimeError(
            f"模型参数的特征维度为 {ckpt_feat_dim}，但当前特征目录 {args.feature_dir} 的维度为 {feat_dim_data}，请检查是否使用了对应的特征目录或模型文件"
        )
    feat_dim = ckpt_feat_dim or feat_dim_data
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(device)
    model.load_state_dict(state, strict=False)

    print("正在提取所有utterance embedding（可能较慢）...")
    embs, labels, spk2idx = extract_all_embeddings(model, device, args.feature_dir)

    print("计算成对得分（抽样）...")
    y, scores, same_scores, diff_scores = compute_pairs_scores(embs, labels, max_pairs=args.max_pairs)

    print("计算 ROC 与 EER ...")
    unique_labels = np.unique(y)
    if len(unique_labels) < 2 or len(scores) == 0:
        print("评估数据不足，无法计算 ROC/EER，已输出空指标")
        out_json = os.path.join(backend_dir, "eer_threshold.json")
        with open(out_json, "w") as f:
            json.dump({"auc": None, "eer": None, "threshold": None}, f, indent=2)
        roc_points_json = os.path.join(backend_dir, "roc_points.json")
        with open(roc_points_json, "w") as f:
            json.dump({"fpr": [], "tpr": [], "thresholds": []}, f, indent=2)
        det_points_json = os.path.join(backend_dir, "det_points.json")
        with open(det_points_json, "w") as f:
            json.dump({"fpr": [], "fnr": []}, f, indent=2)
        mindcf_json = os.path.join(backend_dir, "mindcf.json")
        with open(mindcf_json, "w") as f:
            json.dump({"threshold": None, "min_dcf": None, "dcf": [], "thresholds": []}, f, indent=2)
        score_dist_json = os.path.join(backend_dir, "score_dist.json")
        with open(score_dist_json, "w") as f:
            json.dump({"bins": [], "same": [], "diff": []}, f, indent=2)
        calib_json = os.path.join(backend_dir, "calibration.json")
        with open(calib_json, "w") as f:
            json.dump({"bins": [], "accuracy": [], "confidence": [], "count": [], "ece": None}, f, indent=2)
        sys.exit(0)
    try:
        fpr, tpr, thresholds = roc_curve(y, scores)
        roc_auc = auc(fpr, tpr)
        eer, eer_thr = eer_from_roc(fpr, tpr, thresholds)
        mindcf = compute_mindcf(fpr, tpr, thresholds)
        rec_thr, rec_youden = recommend_threshold(fpr, tpr, thresholds)
    except ValueError as exc:
        print(f"ROC 计算失败：{exc}")
        out_json = os.path.join(backend_dir, "eer_threshold.json")
        with open(out_json, "w") as f:
            json.dump({"auc": None, "eer": None, "threshold": None}, f, indent=2)
        roc_points_json = os.path.join(backend_dir, "roc_points.json")
        with open(roc_points_json, "w") as f:
            json.dump({"fpr": [], "tpr": [], "thresholds": []}, f, indent=2)
        det_points_json = os.path.join(backend_dir, "det_points.json")
        with open(det_points_json, "w") as f:
            json.dump({"fpr": [], "fnr": []}, f, indent=2)
        mindcf_json = os.path.join(backend_dir, "mindcf.json")
        with open(mindcf_json, "w") as f:
            json.dump({"threshold": None, "min_dcf": None, "dcf": [], "thresholds": []}, f, indent=2)
        score_dist_json = os.path.join(backend_dir, "score_dist.json")
        with open(score_dist_json, "w") as f:
            json.dump({"bins": [], "same": [], "diff": []}, f, indent=2)
        calib_json = os.path.join(backend_dir, "calibration.json")
        with open(calib_json, "w") as f:
            json.dump({"bins": [], "accuracy": [], "confidence": [], "count": [], "ece": None}, f, indent=2)
        sys.exit(0)
    if rec_thr is not None:
        print(f"AUC={roc_auc:.4f}  EER={eer:.4f}, suggested threshold={rec_thr:.4f}")
    else:
        print(f"AUC={roc_auc:.4f}  EER={eer:.4f}, suggested threshold={mindcf['threshold']:.4f}")

    # 保存 ROC 图
    plt.figure(figsize=(6,5))
    plt.plot(fpr, tpr, label=f"AUC={roc_auc:.4f}")
    plt.plot([0,1],[0,1],'k--', alpha=0.3)
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.title("ROC")
    plt.legend()
    plt.grid(True)
    out_png = os.path.join(roc_dir, "roc.png")
    plt.savefig(out_png)
    plt.close()
    print("Saved ROC to", out_png)

    out_json = os.path.join(backend_dir, "eer_threshold.json")
    with open(out_json, "w") as f:
        json.dump(
            {
                "auc": float(roc_auc),
                "eer": float(eer),
                "threshold_eer": float(eer_thr),
                "threshold_mindcf": float(mindcf["threshold"]),
                "mindcf": float(mindcf["min_dcf"]),
                "threshold_youden": float(rec_thr) if rec_thr is not None else None,
                "youden": float(rec_youden) if rec_youden is not None else None,
                "threshold": float(rec_thr) if rec_thr is not None else float(mindcf["threshold"]),
                "p_target": float(mindcf["p_target"]),
                "c_miss": float(mindcf["c_miss"]),
                "c_fa": float(mindcf["c_fa"]),
            },
            f,
            indent=2,
        )
    print("Saved metrics to", out_json)

    roc_points_json = os.path.join(backend_dir, "roc_points.json")
    with open(roc_points_json, "w") as f:
        json.dump(
            {
                "fpr": [float(v) for v in fpr],
                "tpr": [float(v) for v in tpr],
                "thresholds": [float(v) for v in thresholds],
            },
            f,
            indent=2,
        )
    print("Saved ROC points to", roc_points_json)

    det_points_json = os.path.join(backend_dir, "det_points.json")
    with open(det_points_json, "w") as f:
        json.dump(
            {
                "fpr": [float(v) for v in fpr],
                "fnr": [float(1 - v) for v in tpr],
            },
            f,
            indent=2,
        )
    print("Saved DET points to", det_points_json)

    mindcf_json = os.path.join(backend_dir, "mindcf.json")
    with open(mindcf_json, "w") as f:
        json.dump(mindcf, f, indent=2)
    print("Saved minDCF to", mindcf_json)

    score_dist_json = os.path.join(backend_dir, "score_dist.json")
    with open(score_dist_json, "w") as f:
        json.dump(compute_score_hist(same_scores, diff_scores), f, indent=2)
    print("Saved score distribution to", score_dist_json)

    calib_json = os.path.join(backend_dir, "calibration.json")
    with open(calib_json, "w") as f:
        json.dump(compute_calibration(scores, y), f, indent=2)
    print("Saved calibration to", calib_json)
