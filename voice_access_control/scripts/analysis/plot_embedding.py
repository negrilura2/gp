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
from voice_engine.config import DEFAULT_MODEL_PATH, EMBEDDING_DIM
from voice_engine.core.dataset import SpeakerDataset, pad_collate
from voice_engine.core.ecapa_tdnn import LightECAPA


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


def run(args):
    """
    Programmatic entry point for plotting embedding.
    args: Namespace-like object with attributes:
        config, model, feature_dir, out_dir, feature_type,
        batch_size, device, method, perplexity, seed,
        max_speakers, max_utts_per_spk
    """
    cfg = {}
    if getattr(args, "config", None):
        with open(args.config, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        print(f"Loading config from {args.config}")

    # Priority: Args > Config > Default
    model_path = getattr(args, "model", None) or cfg.get("model", {}).get("path") or DEFAULT_MODEL_PATH
    # Handle feature_dir being None or empty string
    feature_dir_arg = getattr(args, "feature_dir", None)
    feature_dir = feature_dir_arg or cfg.get("dataset", {}).get("feature_dir") or str(FEATURES_DIR)
    
    out_dir_arg = getattr(args, "out_dir", None)
    out_dir = out_dir_arg or cfg.get("analysis", {}).get("out_dir") or str(REPORTS_DIR)
    
    analysis_cfg = cfg.get("analysis", {})
    emb_cfg = analysis_cfg.get("embedding", {})
    
    feature_type = getattr(args, "feature_type", None) or analysis_cfg.get("feature_type", "mfcc_delta")
    batch_size = getattr(args, "batch_size", None) or analysis_cfg.get("batch_size", 32)
    device = getattr(args, "device", None) or analysis_cfg.get("device", "cuda" if torch.cuda.is_available() else "cpu")
    seed = getattr(args, "seed", None) or analysis_cfg.get("seed", 42)
    
    method = getattr(args, "method", None) or emb_cfg.get("method", "tsne")
    perplexity = getattr(args, "perplexity", None) or emb_cfg.get("perplexity", 30)
    max_speakers = getattr(args, "max_speakers", None) or emb_cfg.get("max_speakers", 10)
    max_utts_per_spk = getattr(args, "max_utts_per_spk", None) or emb_cfg.get("max_utts_per_spk", 10)

    if str(device).lower().startswith("cuda") and not torch.cuda.is_available():
        print("WARNING: CUDA not available, switching to CPU")
        device = "cpu"

    feature_dir = resolve_feature_dir(feature_dir, feature_type)
    if not os.path.isdir(feature_dir):
        # Fallback or error?
        # If running from eval thread, maybe feature_dir is passed correctly.
        pass

    try:
        ds = SpeakerDataset(feature_dir)
    except Exception as e:
        print(f"Dataset load failed: {e}")
        return

    if len(ds) == 0:
        print("feature_dir 内没有可用特征文件")
        return

    sample_feat, _ = ds[0]
    feat_dim_data = int(sample_feat.shape[0])
    
    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
        return
        
    state = torch.load(model_path, map_location=device)
    ckpt_feat_dim = None
    w = state.get("layer1.conv.weight")
    if w is not None:
        ckpt_feat_dim = int(w.shape[1])
    if ckpt_feat_dim is not None and ckpt_feat_dim != feat_dim_data:
        print(f"Warning: Model expects {ckpt_feat_dim} but data has {feat_dim_data}")
    feat_dim = ckpt_feat_dim or feat_dim_data
    model = LightECAPA(feat_dim=feat_dim, emb_dim=EMBEDDING_DIM, n_speakers=None).to(device)
    model.load_state_dict(state, strict=False)
    model.eval()

    # Need a way to select indices... SpeakerDataset has no direct way to filter inside?
    # select_indices logic is external in this file.
    # We need to reimplement or call it.
    # But wait, select_indices IS defined in this file (global scope).
    indices = select_indices(ds, max_speakers, max_utts_per_spk, seed)
    subset = Subset(ds, indices) if indices else ds
    loader = DataLoader(subset, batch_size=batch_size, shuffle=False, collate_fn=pad_collate)

    all_embs = []
    all_labels = []
    
    # Check if dataset is empty
    if len(subset) == 0:
        print("No samples selected for plotting.")
        return

    with torch.no_grad():
        for feats, lengths, labels_batch in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            all_embs.append(emb.cpu().numpy())
            all_labels.append(labels_batch.numpy())

    if not all_embs:
        print("No embeddings extracted.")
        return

    embeddings = np.vstack(all_embs)
    labels = np.hstack(all_labels)
    if embeddings.shape[0] < 3:
        print("样本过少，无法进行降维可视化")
        return

    points = reduce_embeddings(embeddings, method, seed, perplexity)
    out_root = os.path.join(out_dir, "plots", "embedding")
    os.makedirs(out_root, exist_ok=True)
    # Use a fixed name or pattern so frontend can find it easily?
    # Frontend looks for {method}_{feature_type}_{model_name}.png
    # But model_name might vary.
    # Ideally, we should use a consistent naming if possible, OR
    # frontend uses glob to find latest.
    model_name = os.path.splitext(os.path.basename(model_path))[0]
    
    # Updated naming convention: {method}_{feature_type}_{score_norm}_{model_name}
    # If score_norm is 'none', we can omit it or keep it for consistency.
    # Let's keep it to match user request.
    score_norm = getattr(args, "score_norm", "none")
    stem = f"{method}_{feature_type}_{score_norm}_{model_name}"
    out_png = os.path.join(out_root, f"{stem}.png")
    out_json = os.path.join(out_root, f"{stem}.json")
    
    idx2spk = {v: k for k, v in ds.spk2idx.items()}
    plot_title = f"Embedding {method.upper()} (n={len(labels)})"
    if score_norm != "none":
        plot_title += f" [{score_norm.upper()}]"
        
    plot_embeddings(points, labels, idx2spk, out_png, plot_title)

    payload = [
        {"x": float(x), "y": float(y), "label": int(lab), "spk": idx2spk.get(int(lab), str(lab))}
        for (x, y), lab in zip(points, labels)
    ]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved: {out_png}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", help="Path to config yaml file")
    parser.add_argument("--model", default=None)
    parser.add_argument("--feature_dir", default=None)
    parser.add_argument("--out_dir", default=None)
    parser.add_argument("--feature_type", choices=["mfcc", "mfcc_delta", "logmel"], default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--method", choices=["tsne", "pca"], default=None)
    parser.add_argument("--perplexity", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max_speakers", type=int, default=None)
    parser.add_argument("--max_utts_per_spk", type=int, default=None)
    parser.add_argument("--score_norm", choices=["none", "znorm", "tnorm", "snorm"], default=None, help="Tag for score normalization strategy")
    args = parser.parse_args()
    
    run(args)

