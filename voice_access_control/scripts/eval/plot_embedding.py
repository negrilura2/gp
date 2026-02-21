import argparse
import json
import os
import sys

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from torch.utils.data import DataLoader, Subset

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import FEATURES_DIR, REPORTS_DIR
from voice_engine.config import DEFAULT_MODEL_PATH
from voice_engine.dataset import SpeakerDataset, pad_collate
from voice_engine.ecapa_tdnn import LightECAPA


def resolve_feature_dir(feature_dir, feature_type):
    if not os.path.isdir(feature_dir):
        return feature_dir
    base_name = os.path.basename(os.path.normpath(feature_dir))
    feature_names = {"mfcc", "mfcc_delta", "logmel"}
    if base_name not in feature_names:
        cand = os.path.join(feature_dir, feature_type)
        if os.path.isdir(cand):
            return cand
    return feature_dir


def select_indices(ds, max_speakers, max_utts_per_spk, seed):
    rng = np.random.RandomState(seed)
    label_to_indices = {}
    for i, (_, label) in enumerate(ds.samples):
        label_to_indices.setdefault(label, []).append(i)
    labels = list(label_to_indices.keys())
    if max_speakers and max_speakers > 0 and len(labels) > max_speakers:
        labels = list(rng.choice(labels, size=max_speakers, replace=False))
    indices = []
    for label in labels:
        idxs = label_to_indices[label]
        if max_utts_per_spk and max_utts_per_spk > 0 and len(idxs) > max_utts_per_spk:
            idxs = rng.choice(idxs, size=max_utts_per_spk, replace=False).tolist()
        indices.extend(idxs)
    return indices


def reduce_embeddings(embeddings, method, seed, perplexity):
    if method == "pca":
        try:
            from sklearn.decomposition import PCA
        except Exception as exc:
            raise RuntimeError("需要安装 scikit-learn 才能使用 PCA") from exc
        reducer = PCA(n_components=2, random_state=seed)
        return reducer.fit_transform(embeddings)
    try:
        from sklearn.manifold import TSNE
    except Exception as exc:
        raise RuntimeError("需要安装 scikit-learn 才能使用 t-SNE") from exc
    n_samples = embeddings.shape[0]
    max_perp = max(2, (n_samples - 1) // 3)
    perp = min(perplexity, max_perp)
    if perp >= n_samples:
        perp = max(2, n_samples - 1)
    reducer = TSNE(n_components=2, random_state=seed, perplexity=perp, init="pca", learning_rate="auto")
    return reducer.fit_transform(embeddings)


def plot_embeddings(points, labels, idx2spk, out_png, title):
    plt.figure(figsize=(8, 6))
    unique_labels = sorted(set(labels))
    colors = plt.cm.get_cmap("tab20", len(unique_labels))
    for i, lab in enumerate(unique_labels):
        mask = labels == lab
        plt.scatter(points[mask, 0], points[mask, 1], s=18, alpha=0.8, color=colors(i), label=idx2spk.get(int(lab), str(lab)))
    plt.title(title)
    plt.xlabel("Dim 1")
    plt.ylabel("Dim 2")
    if len(unique_labels) <= 15:
        plt.legend(loc="best", fontsize=8)
    plt.tight_layout()
    plt.savefig(out_png, dpi=160)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--feature_dir", default=str(FEATURES_DIR))
    parser.add_argument("--out_dir", default=str(REPORTS_DIR))
    parser.add_argument("--feature_type", choices=["mfcc", "mfcc_delta", "logmel"], default="mfcc_delta")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--method", choices=["tsne", "pca"], default="tsne")
    parser.add_argument("--perplexity", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_speakers", type=int, default=10)
    parser.add_argument("--max_utts_per_spk", type=int, default=10)
    args = parser.parse_args()

    if str(args.device).lower().startswith("cuda") and not torch.cuda.is_available():
        print("WARNING: CUDA not available, switching to CPU")
        args.device = "cpu"

    feature_dir = resolve_feature_dir(args.feature_dir, args.feature_type)
    ds = SpeakerDataset(feature_dir)
    if len(ds) == 0:
        raise ValueError("feature_dir 内没有可用特征文件")

    sample_feat, _ = ds[0]
    feat_dim_data = int(sample_feat.shape[0])
    state = torch.load(args.model, map_location=args.device)
    ckpt_feat_dim = None
    w = state.get("layer1.conv.weight")
    if w is not None:
        ckpt_feat_dim = int(w.shape[1])
    if ckpt_feat_dim is not None and ckpt_feat_dim != feat_dim_data:
        print(f"Warning: Model expects {ckpt_feat_dim} but data has {feat_dim_data}")
    feat_dim = ckpt_feat_dim or feat_dim_data
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(args.device)
    model.load_state_dict(state, strict=False)
    model.eval()

    indices = select_indices(ds, args.max_speakers, args.max_utts_per_spk, args.seed)
    subset = Subset(ds, indices) if indices else ds
    loader = DataLoader(subset, batch_size=args.batch_size, shuffle=False, collate_fn=pad_collate)

    all_embs = []
    all_labels = []
    with torch.no_grad():
        for feats, lengths, labels in loader:
            feats = feats.to(args.device)
            lengths = lengths.to(args.device)
            emb = model(feats, lengths, return_embedding=True)
            all_embs.append(emb.cpu().numpy())
            all_labels.append(labels.numpy())

    embeddings = np.vstack(all_embs)
    labels = np.hstack(all_labels)
    if embeddings.shape[0] < 3:
        raise ValueError("样本过少，无法进行降维可视化")

    points = reduce_embeddings(embeddings, args.method, args.seed, args.perplexity)
    out_root = os.path.join(args.out_dir, "plots", "embedding")
    os.makedirs(out_root, exist_ok=True)
    stem = f"embedding_{args.method}"
    out_png = os.path.join(out_root, f"{stem}.png")
    out_json = os.path.join(out_root, f"{stem}.json")

    idx2spk = {v: k for k, v in ds.spk2idx.items()}
    plot_embeddings(points, labels, idx2spk, out_png, f"Embedding {args.method.upper()} (n={len(labels)})")

    payload = [
        {"x": float(x), "y": float(y), "label": int(lab), "spk": idx2spk.get(int(lab), str(lab))}
        for (x, y), lab in zip(points, labels)
    ]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved: {out_png}")
    print(f"Saved: {out_json}")


if __name__ == "__main__":
    main()
