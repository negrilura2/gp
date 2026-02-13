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
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import FEATURES_DIR, MODELS_DIR, REPORTS_DIR

from model.ecapa_tdnn import LightECAPA
from model.dataset import SpeakerDataset, pad_collate
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
    return y, scores

def eer_from_roc(fpr, tpr, thresholds):
    # fnr = 1 - tpr
    fnr = 1 - tpr
    abs_diffs = np.abs(fpr - fnr)
    idx = np.argmin(abs_diffs)
    eer = (fpr[idx] + fnr[idx]) / 2.0
    thr = thresholds[idx]
    return eer, thr

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.path.join(MODELS_DIR, "ecapa_best.pth"))
    parser.add_argument("--feature_dir", default=str(FEATURES_DIR))
    parser.add_argument("--out_dir", default=str(REPORTS_DIR))
    parser.add_argument("--max_pairs", type=int, default=20000)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    print("加载模型...")
    model = LightECAPA(feat_dim=39, emb_dim=192, n_speakers=None).to(device)
    state = torch.load(args.model, map_location=device)
    model.load_state_dict(state, strict=False)

    print("正在提取所有utterance embedding（可能较慢）...")
    embs, labels, spk2idx = extract_all_embeddings(model, device, args.feature_dir)

    print("计算成对得分（抽样）...")
    y, scores = compute_pairs_scores(embs, labels, max_pairs=args.max_pairs)

    print("计算 ROC 与 EER ...")
    fpr, tpr, thresholds = roc_curve(y, scores)
    roc_auc = auc(fpr, tpr)
    eer, eer_thr = eer_from_roc(fpr, tpr, thresholds)
    print(f"AUC={roc_auc:.4f}  EER={eer:.4f}, suggested threshold={eer_thr:.4f}")

    # 保存 ROC 图
    plt.figure(figsize=(6,5))
    plt.plot(fpr, tpr, label=f"AUC={roc_auc:.4f}")
    plt.plot([0,1],[0,1],'k--', alpha=0.3)
    plt.xlabel("FPR")
    plt.ylabel("TPR")
    plt.title("ROC")
    plt.legend()
    plt.grid(True)
    out_png = os.path.join(args.out_dir, "roc.png")
    plt.savefig(out_png)
    plt.close()
    print("Saved ROC to", out_png)

    out_json = os.path.join(args.out_dir, "eer_threshold.json")
    with open(out_json, "w") as f:
        json.dump({"auc": float(roc_auc), "eer": float(eer), "threshold": float(eer_thr)}, f, indent=2)
    print("Saved metrics to", out_json)
