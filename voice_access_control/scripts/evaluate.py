# scripts/eval/eval_threshold.py
"""
Usage:
python -m scripts.eval.eval_threshold --config configs/eval.yaml
python -m scripts.eval.eval_threshold --model models/ecapa_best.pth --feature_dir data/features --out_dir reports --max_pairs 20000

Outputs:
reports/roc.png
reports/eer_threshold.json  ({"eer":..., "threshold":...})
"""
import argparse
import os
import sys
import json
import yaml
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

from voice_engine.core.ecapa_tdnn import LightECAPA
from voice_engine.core.dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader
from voice_engine.core.metrics import extract_all_embeddings
from voice_engine.core.metrics import (
    compute_pairs_scores,
    compute_cohort_stats,
    apply_score_norm,
    eer_from_roc,
    compute_mindcf,
    recommend_threshold,
    compute_score_hist,
    compute_calibration,
)

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def build_eval_bundle(y, scores, same_scores, diff_scores):
    fpr, tpr, thresholds = roc_curve(y, scores, pos_label=1)
    roc_auc = auc(fpr, tpr)
    eer, eer_threshold = eer_from_roc(fpr, tpr, thresholds)
    mindcf_res = compute_mindcf(fpr, tpr, thresholds)
    rec_thr, youden_val = recommend_threshold(fpr, tpr, thresholds)
    score_dist_res = compute_score_hist(same_scores, diff_scores)
    calib_res = compute_calibration(scores, y)
    roc_data = {
        "fpr": [float(x) for x in fpr],
        "tpr": [float(x) for x in tpr],
        "thresholds": [float(x) for x in thresholds]
    }
    fnr = 1 - tpr
    det_data = {
        "fpr": [float(x) for x in fpr],
        "fnr": [float(x) for x in fnr],
        "thresholds": [float(x) for x in thresholds]
    }
    metrics = {
        "auc": float(roc_auc),
        "eer": float(eer),
        "threshold_eer": float(eer_threshold),
        "threshold_mindcf": mindcf_res["threshold"],
        "mindcf": mindcf_res["min_dcf"],
        "threshold_youden": rec_thr,
        "youden": youden_val,
        "threshold": rec_thr if rec_thr is not None else float(eer_threshold),
        "p_target": mindcf_res["p_target"],
        "c_miss": mindcf_res["c_miss"],
        "c_fa": mindcf_res["c_fa"],
    }
    return {
        "fpr": fpr,
        "tpr": tpr,
        "thresholds": thresholds,
        "roc_auc": roc_auc,
        "eer": eer,
        "eer_threshold": eer_threshold,
        "mindcf_res": mindcf_res,
        "score_dist_res": score_dist_res,
        "calib_res": calib_res,
        "roc_data": roc_data,
        "det_data": det_data,
        "metrics": metrics,
    }

def build_cohort_indices(labels, max_speakers, max_utts_per_spk, seed):
    rng = np.random.RandomState(seed)
    label_to_indices = {}
    for idx, lb in enumerate(labels):
        label_to_indices.setdefault(lb, []).append(idx)
    all_labels = list(label_to_indices.keys())
    if max_speakers and max_speakers > 0 and len(all_labels) > max_speakers:
        all_labels = list(rng.choice(all_labels, size=max_speakers, replace=False))
    indices = []
    for lb in all_labels:
        idxs = label_to_indices[lb]
        if max_utts_per_spk and max_utts_per_spk > 0 and len(idxs) > max_utts_per_spk:
            idxs = rng.choice(idxs, size=max_utts_per_spk, replace=False).tolist()
        indices.extend(idxs)
    return indices

def build_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", help="Path to config yaml file")
    
    parser.add_argument("--model", help="Model path")
    parser.add_argument("--feature_dir", help="Feature directory")
    parser.add_argument("--out_dir", help="Output directory")
    parser.add_argument("--max_pairs", type=int, help="Max pairs for EER")
    parser.add_argument("--noise_dir", help="Noise directory for augmentation")
    parser.add_argument("--score_norm", choices=["none", "znorm", "tnorm", "snorm"], help="Score normalization method")
    parser.add_argument("--cohort_speakers", type=int, help="Number of speakers for cohort")
    parser.add_argument("--cohort_utts_per_spk", type=int, help="Utterances per speaker for cohort")
    parser.add_argument("--cohort_seed", type=int, help="Random seed for cohort")
    return parser

class EvalArgs:
    def __init__(self, args, cfg):
        # Priorities: CLI arg > Config value > Default
        
        # Model
        self.model = args.model or cfg.get("model", {}).get("path") or str(MODELS_DIR / "ecapa_best.pth")
        
        # Data
        self.feature_dir = args.feature_dir or cfg.get("dataset", {}).get("feature_dir") or str(FEATURES_DIR)
        self.out_dir = args.out_dir or cfg.get("paths", {}).get("out_dir") or str(REPORTS_DIR)
        self.noise_dir = args.noise_dir or cfg.get("dataset", {}).get("noise_dir")
        
        # Params
        self.max_pairs = args.max_pairs or cfg.get("evaluation", {}).get("max_pairs", 20000)
        
        # Score Norm
        self.score_norm = args.score_norm or cfg.get("evaluation", {}).get("score_norm", "none")
        
        # Cohort
        self.cohort_speakers = args.cohort_speakers or cfg.get("evaluation", {}).get("cohort_speakers", 20)
        self.cohort_utts_per_spk = args.cohort_utts_per_spk or cfg.get("evaluation", {}).get("cohort_utts_per_spk", 5)
        self.cohort_seed = args.cohort_seed or cfg.get("evaluation", {}).get("cohort_seed", 42)

def run(args):
    os.makedirs(args.out_dir, exist_ok=True)
    
    device = "cuda" if torch.cuda.is_available() else "cpu"

    augmentor = None
    mode = 'feature'
    if args.noise_dir:
        from voice_engine.dataset import NoiseAugmentor
        augmentor = NoiseAugmentor(args.noise_dir)
        print(f"Noise Augmentation Enabled for Evaluation: {args.noise_dir}")
        if args.feature_dir == str(FEATURES_DIR) or args.feature_dir == "data/features":
             print("Info: Switching data source to 'data/processed' for raw wav loading.")
             args.feature_dir = "data/processed"
        mode = 'raw'

    # Check feature dimension
    # Create temp ds to check dimension
    ds_tmp = SpeakerDataset(args.feature_dir, mode=mode, augmentor=augmentor, limit=1)
    if len(ds_tmp) == 0 and mode == 'feature':
        # Try finding subdirectory (e.g. mfcc_delta)
        for sub in ["mfcc_delta", "mfcc", "logmel"]:
            candidate = os.path.join(args.feature_dir, sub)
            if os.path.isdir(candidate):
                ds_check = SpeakerDataset(candidate, mode=mode, augmentor=augmentor, limit=1)
                if len(ds_check) > 0:
                    print(f"Info: Auto-switching feature_dir to '{candidate}'")
                    args.feature_dir = candidate
                    ds_tmp = ds_check
                    break

    if len(ds_tmp) == 0:
        raise ValueError(f"feature_dir '{args.feature_dir}' 内没有可用文件 (mode={mode})")
    sample_feat, _ = ds_tmp[0]
    feat_dim_data = int(sample_feat.shape[0])
    print(f"Detected Feature Dim: {feat_dim_data}")

    print("加载模型...")
    if not os.path.exists(args.model):
        raise FileNotFoundError(f"Model file not found: {args.model}")
        
    state = torch.load(args.model, map_location=device)
    ckpt_feat_dim = None
    w = state.get("layer1.conv.weight")
    if w is not None:
        ckpt_feat_dim = int(w.shape[1])
    if ckpt_feat_dim is not None and ckpt_feat_dim != feat_dim_data:
        print(f"Warning: Model expects {ckpt_feat_dim} but data has {feat_dim_data}. Proceeding if model handles it (e.g. strict=False load), but this might be an error.")
        pass

    # Use model's dim if known, else data's
    feat_dim = ckpt_feat_dim or feat_dim_data
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(device)
    model.load_state_dict(state, strict=False)

    print("正在提取所有utterance embedding（可能较慢）...")
    embs, labels, spk2idx = extract_all_embeddings(model, device, args.feature_dir, mode=mode, augmentor=augmentor)

    print("计算成对得分（抽样）...")
    y, scores, same_scores, diff_scores, pair_indices = compute_pairs_scores(
        embs,
        labels,
        max_pairs=args.max_pairs,
        seed=42,
        return_indices=True,
    )

    norm_method = args.score_norm
    norm_scores = None
    norm_same_scores = None
    norm_diff_scores = None
    norm_stats = None
    if norm_method != "none":
        cohort_indices = build_cohort_indices(labels, args.cohort_speakers, args.cohort_utts_per_spk, args.cohort_seed)
        if len(cohort_indices) < 2:
            print("WARNING: Cohort 样本过少，跳过归一化")
            norm_method = "none"
        else:
            cohort_embs = embs[cohort_indices]
            cohort_labels = labels[cohort_indices]
            mu, sigma = compute_cohort_stats(embs, labels, cohort_embs, cohort_labels)
            norm_scores = apply_score_norm(scores, pair_indices, mu, sigma, method=norm_method)
            norm_same_scores = norm_scores[y == 1]
            norm_diff_scores = norm_scores[y == 0]
            norm_stats = {
                "method": norm_method,
                "cohort_size": int(len(cohort_indices)),
                "cohort_speakers": int(len(set(cohort_labels.tolist()))),
                "cohort_utts_per_spk": int(args.cohort_utts_per_spk),
            }

    print("计算 ROC 与 EER ...")
    unique_labels = np.unique(y)
    if len(unique_labels) < 2 or len(scores) == 0:
        print("评估数据不足，无法计算 ROC/EER，已输出空指标")
        sys.exit(0)
        
    raw_bundle = build_eval_bundle(y, scores, same_scores, diff_scores)
    print(f"AUC: {raw_bundle['roc_auc']:.4f}")
    print(f"EER: {raw_bundle['eer']:.4f} @ threshold={raw_bundle['eer_threshold']:.4f}")
    norm_bundle = None
    if norm_scores is not None:
        norm_bundle = build_eval_bundle(y, norm_scores, norm_same_scores, norm_diff_scores)
    
    # Define output directories
    # Use backend_responses/{method} subdirectory to match backend expectation
    backend_dir = os.path.join(args.out_dir, "backend_responses", args.score_norm)
    os.makedirs(backend_dir, exist_ok=True)
    
    # Save ROC plot (legacy location in reports root, also save to backend_responses for consistency if needed, but backend doesn't read png from there)
    plt.figure()
    plt.plot(raw_bundle["fpr"], raw_bundle["tpr"], color='darkorange', lw=2, label=f'ROC curve (area = {raw_bundle["roc_auc"]:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'ROC ({args.score_norm})')
    plt.legend(loc="lower right")
    plt.savefig(os.path.join(backend_dir, "roc.png"))
    print(f"Saved ROC to {os.path.join(backend_dir, 'roc.png')}")
    
    # Save results to the specific method directory
    final_bundle = norm_bundle if norm_scores is not None else raw_bundle
    
    # 1. Compute & Save MinDCF
    with open(os.path.join(backend_dir, "mindcf.json"), "w") as f:
        json.dump(final_bundle["mindcf_res"], f, indent=2)

    # 2. Compute & Save Score Distribution
    with open(os.path.join(backend_dir, "score_dist.json"), "w") as f:
        json.dump(final_bundle["score_dist_res"], f, indent=2)
        
    # 3. Compute & Save Calibration
    with open(os.path.join(backend_dir, "calibration.json"), "w") as f:
        json.dump(final_bundle["calib_res"], f, indent=2)

    # 4. Save ROC Points
    with open(os.path.join(backend_dir, "roc_points.json"), "w") as f:
        json.dump(final_bundle["roc_data"], f, indent=2)
        
    # 5. Save DET Points (FPR vs FNR)
    with open(os.path.join(backend_dir, "det_points.json"), "w") as f:
        json.dump(final_bundle["det_data"], f, indent=2)

    # 6. Save EER & Metrics (Main Entry)
    metrics = dict(final_bundle["metrics"])
    metrics["augment"] = bool(args.noise_dir)
    metrics["method"] = args.score_norm
    if norm_stats:
        metrics["score_norm"] = norm_stats
        
    with open(os.path.join(backend_dir, "eer_threshold.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    
    # Also save to legacy metrics.json in root for backward compatibility if needed
    with open(os.path.join(args.out_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    score_norm_dir = os.path.join(args.out_dir, "score_norm")
    os.makedirs(score_norm_dir, exist_ok=True)
    with open(os.path.join(score_norm_dir, f"{args.score_norm}.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    
    print(f"Saved backend responses to {backend_dir}")

def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    
    cfg = {}
    if args.config:
        if not os.path.exists(args.config):
            print(f"Error: Config file not found: {args.config}")
            sys.exit(1)
        print(f"Loading config from {args.config}")
        cfg = load_config(args.config)
        
    eval_args = EvalArgs(args, cfg)
    
    print(f"Starting evaluation...")
    print(f"  Model: {eval_args.model}")
    print(f"  Data: {eval_args.feature_dir}")
    print(f"  Output: {eval_args.out_dir}")
    print(f"  Norm: {eval_args.score_norm}")
    
    run(eval_args)

if __name__ == "__main__":
    main()
