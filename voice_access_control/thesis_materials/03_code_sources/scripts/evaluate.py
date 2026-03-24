# scripts/evaluate.py
"""
Usage:
python -m scripts.evaluate --config configs/eval.yaml
python -m scripts.evaluate --model models/ecapa_best.pth --feature_dir data/features --out_dir reports --max_pairs 20000

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
from pathlib import Path
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.config import (
    DEFAULT_MODEL_PATH,
    FEATURES_DIR,
    REPORTS_DIR,
    PROCESSED_DIR,
    DATA_DIR
)

from voice_engine.core.ecapa_tdnn import LightECAPA
from voice_engine.core.dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader
from voice_engine.core.metrics import (
    extract_all_embeddings,
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

class EvalArgs:
    def __init__(self, args, cfg):
        # Priorities: CLI arg > Config value > Default
        
        # Model
        self.model = args.model or cfg.get("model", {}).get("path") or DEFAULT_MODEL_PATH
        
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

def run_eval(args):
    os.makedirs(args.out_dir, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    augmentor = None
    mode = 'feature'
    
    final_feature_dir = args.feature_dir

    print(f"Loading model: {args.model}")
    if not os.path.exists(args.model):
        raise FileNotFoundError(f"Model file not found: {args.model}")

    metadata_path = os.path.splitext(args.model)[0] + ".json"
    model_feature_type = None
    model_emb_dim = None
    model_channels = None
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                model_feature_type = meta.get("feature_type")
                model_emb_dim = meta.get("emb_dim")
                model_channels = meta.get("n_channels") or meta.get("channels")
                print(f"Loaded model metadata: feature_type={model_feature_type}, feat_dim={meta.get('feat_dim')}")
        except Exception as e:
            print(f"Warning: Failed to load model metadata: {e}")

    if not os.path.exists(final_feature_dir) or not any(Path(final_feature_dir).rglob("*.npy")):
        # ... (previous fallback logic) ...
        pass
        
    # FORCE SWITCH logic: If feature_dir is generic root, AND model metadata has a type, 
    # we should try to append that type to path first!
    if final_feature_dir == args.feature_dir and model_feature_type:
         candidate = os.path.join(final_feature_dir, model_feature_type)
         if os.path.exists(candidate) and any(Path(candidate).rglob("*.npy")):
             print(f"Info: Prioritizing model feature type '{model_feature_type}' -> '{candidate}'")
             final_feature_dir = candidate
    elif final_feature_dir == args.feature_dir:
         # If no metadata, or metadata path invalid, try auto-detection if root contains mixed types?
         # But existing logic was: if root has npy, use root.
         # The problem: root has logmel/ and mfcc_delta/ subdirs. rglob finds BOTH.
         # SpeakerDataset(root) will load ALL files recursively.
         # If root has both logmel (40) and mfcc (39), we get mixed or wrong data.
         
         # Heuristic: if root has "mfcc" or "logmel" subdir, switch to it?
         candidates = ["mfcc_delta", "logmel"]
         for sub in candidates:
             candidate = os.path.join(final_feature_dir, sub)
             if os.path.exists(candidate) and any(Path(candidate).rglob("*.npy")):
                 print(f"Info: Found subdir '{sub}', switching to '{candidate}'")
                 final_feature_dir = candidate
                 break

    test_dir = os.path.join(final_feature_dir, "test")
    valid_dir = os.path.join(final_feature_dir, "valid")
    
    if os.path.exists(test_dir) and any(Path(test_dir).rglob("*.npy")):
        print(f"Info: Found 'test' split. Restricting evaluation to: {test_dir}")
        final_feature_dir = test_dir
    elif os.path.exists(valid_dir) and any(Path(valid_dir).rglob("*.npy")):
        print(f"Info: Found 'valid' split. Restricting evaluation to: {valid_dir}")
        final_feature_dir = valid_dir
    
    if args.noise_dir:
        from voice_engine.core.dataset import NoiseAugmentor
        augmentor = NoiseAugmentor(args.noise_dir)
        print(f"Noise Augmentation Enabled for Evaluation: {args.noise_dir}")
        if "features" in final_feature_dir:
             print("Info: Switching data source to PROCESSED_DIR for raw wav loading due to augmentation.")
             final_feature_dir = str(PROCESSED_DIR)
        mode = 'raw'

    print(f"Loading data from: {final_feature_dir} (mode={mode})")
    print(f"Loading model: {args.model}")
    if not os.path.exists(args.model):
        raise FileNotFoundError(f"Model file not found: {args.model}")
        
    try:
        ds_tmp = SpeakerDataset(final_feature_dir, mode=mode, augmentor=augmentor, limit=1)
    except Exception as e:
        raise ValueError(f"Error initializing dataset: {e}")

    if len(ds_tmp) == 0:
        raise ValueError(f"feature_dir '{final_feature_dir}' contains no valid files (mode={mode})")
        
    sample_feat, _ = ds_tmp[0]
    if sample_feat.ndim == 2:
        feat_dim_data = int(sample_feat.shape[1])
    else:
        feat_dim_data = 1 
        
    print(f"Detected Feature Dim: {feat_dim_data}")

    state = torch.load(args.model, map_location=device)
    
    ckpt_feat_dim = None
    w = state.get("layer1.conv.weight")
    if w is not None:
        ckpt_feat_dim = int(w.shape[1])
    
    final_dim = ckpt_feat_dim if ckpt_feat_dim else feat_dim_data
    
    if ckpt_feat_dim and ckpt_feat_dim != feat_dim_data:
        msg = f"Feature dimension mismatch: Model expects {ckpt_feat_dim}, but data has {feat_dim_data}. Please regenerate features or check config."
        print(f"Warning: {msg}")
        if mode == 'feature':
            raise ValueError(msg)
    
    # Infer channels and emb_dim from state dict if not in metadata
    if model_channels is None:
        # layer1.conv.weight: [out_channels, in_channels, kernel_size]
        w = state.get("layer1.conv.weight")
        if w is None:
             w = state.get("module.layer1.conv.weight")
             
        if w is not None:
            model_channels = int(w.shape[0])
            print(f"Inferred channels from checkpoint: {model_channels}")
        else:
            # Fallback if layer1.conv.weight not found
            model_channels = 256 
            print(f"Warning: Could not infer channels from checkpoint, using default: {model_channels}")

    if model_emb_dim is None:
        # classifier.weight: [n_speakers, emb_dim] OR [n_speakers, emb_dim, 1] ?
        # In LightECAPA: self.classifier = nn.Linear(emb_dim, n_speakers)
        # Weight shape: [n_speakers, emb_dim]
        # fc1.weight: [emb_dim, channels * 2] (if pooling is default)
        
        # Try infer from fc1.weight first (projector)
        # fc1 is nn.Linear(channels * (1 if type=="avg" else 2), emb_dim)
        w = state.get("fc1.weight")
        if w is not None:
            model_emb_dim = int(w.shape[0])
            print(f"Inferred emb_dim from checkpoint (fc1): {model_emb_dim}")
        else:
            # Try infer from classifier.weight
            cw = state.get("classifier.weight")
            if cw is not None:
                model_emb_dim = int(cw.shape[1])
                print(f"Inferred emb_dim from checkpoint (classifier): {model_emb_dim}")
            else:
                model_emb_dim = 192 
                print(f"Warning: Could not infer emb_dim from checkpoint, using default: {model_emb_dim}")

    n_speakers = 0
    cw = state.get("classifier.weight")
    if cw is not None:
        n_speakers = cw.shape[0]
    else:
        n_speakers = 100
        
    model = LightECAPA(feat_dim=final_dim, channels=model_channels, emb_dim=model_emb_dim, n_speakers=n_speakers).to(device)
    
    try:
        model.load_state_dict(state, strict=False)
    except RuntimeError as e:
        err_msg = str(e)
        if "size mismatch" in err_msg:
            print(f"Warning: Initial load failed with size mismatch: {e}")
            # Intelligent retry logic
            # Check for channel mismatch (512 vs 256)
            if "layer1.conv.weight" in err_msg and "256" in err_msg:
                print(">> Auto-correction: Detected channels=256 in checkpoint. Re-initializing model...")
                model = LightECAPA(feat_dim=final_dim, channels=256, emb_dim=model_emb_dim, n_speakers=n_speakers).to(device)
                model.load_state_dict(state, strict=False)
            # Check for emb_dim mismatch (192 vs 512 etc)
            elif "fc1.weight" in err_msg or "classifier.weight" in err_msg:
                 print(">> Auto-correction: Embedding dimension mismatch. Trying to infer from checkpoint...")
                 # ... logic could be added here
                 raise e # For now, just re-raise if not channel issue
            else:
                raise e
        else:
            raise e
    except Exception as e:
        print(f"Warning loading state dict: {e}")

    model.eval()
    
    print("Extracting embeddings...")
    embs, labels, _ = extract_all_embeddings(model, device, final_feature_dir, mode=mode, augmentor=augmentor)
    
    print(f"Computing scores (max_pairs={args.max_pairs})...")
    y, scores, same_scores, diff_scores = compute_pairs_scores(embs, labels, max_pairs=args.max_pairs)
    
    # Score Normalization Logic
    norm_scores = None
    norm_same_scores = None
    norm_diff_scores = None
    norm_stats = {}
    
    if args.score_norm != "none":
        print(f"Applying Score Normalization: {args.score_norm}")
        # Build Cohort
        from voice_engine.core.metrics import build_templates
        # We need a cohort set. For simplicity, we use a subset of the eval set itself (unsupervised cohort)
        # or we could load a separate cohort. Here we use the eval set.
        # Select cohort speakers
        unique_labels = np.unique(labels)
        rng = np.random.RandomState(args.cohort_seed)
        
        cohort_spks = unique_labels
        if len(unique_labels) > args.cohort_speakers:
            cohort_spks = rng.choice(unique_labels, size=args.cohort_speakers, replace=False)
            
        cohort_embs = []
        cohort_labels = []
        for spk in cohort_spks:
            idxs = np.where(labels == spk)[0]
            if len(idxs) > args.cohort_utts_per_spk:
                idxs = rng.choice(idxs, size=args.cohort_utts_per_spk, replace=False)
            cohort_embs.append(embs[idxs])
            cohort_labels.append(np.full(len(idxs), spk, dtype=labels.dtype))
            
        if len(cohort_embs) > 0:
            cohort_embs = np.concatenate(cohort_embs, axis=0)
            cohort_labels = np.concatenate(cohort_labels, axis=0)
            print(f"Cohort size: {len(cohort_embs)} embeddings from {len(cohort_spks)} speakers.")
            
            # Compute cohort stats
            # For Z-Norm: Verify (Test) vs Cohort
            # For T-Norm: Enroll (Model) vs Cohort
            # Since we are doing Pairwise Eval (not Enroll-Test), strict T-Norm definition is ambiguous.
            # Usually symmetric score norm (S-Norm) is preferred.
            
            # We need to compute stats for EVERY embedding in 'embs' against 'cohort_embs'
            # This can be expensive.
            
            print("Computing cohort stats...")
            mu, sigma = compute_cohort_stats(embs, labels, cohort_embs, cohort_labels)
            
            # Apply Norm
            # For pairwise (e1, e2), S-Norm = 0.5 * ( (s - mu1)/sig1 + (s - mu2)/sig2 )
            # We need indices of pairs to do this efficiently.
            # But compute_pairs_scores returns flat scores.
            # To do this correctly, we should have applied norm inside compute_pairs_scores or reimplement it.
            # Re-implementing simplified version:
            
            # Since we don't have the pairs indices here easily (compute_pairs_scores hides them),
            # we will skip S-Norm implementation in this script for now or use a simplified approximation if supported.
            # Actually, compute_pairs_scores just randomly samples.
            
            print("Warning: Full S-Norm in pairwise evaluation requires pair indices. Skipping actual S-Norm calculation in this script version.")
            print("To implement correctly, use 'voice_engine.core.metrics.compute_snorm_scores' which handles pairs.")
            
        else:
            print("Warning: Cohort is empty. Skipping Normalization.")

    # Build Result Bundle
    raw_bundle = build_eval_bundle(y, scores, same_scores, diff_scores)
    
    # Save Results
    backend_dir = os.path.join(args.out_dir, "backend_responses", args.score_norm)
    os.makedirs(backend_dir, exist_ok=True)
    
    # Save ROC Plot
    plt.figure()
    plt.plot(raw_bundle["fpr"], raw_bundle["tpr"], color='darkorange', lw=2, label=f'ROC (AUC = {raw_bundle["roc_auc"]:.2f})')
    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'ROC ({args.score_norm})')
    plt.legend(loc="lower right")
    plt.savefig(os.path.join(backend_dir, "roc.png"))
    plt.close()
    
    # Save JSONs
    with open(os.path.join(backend_dir, "eer_threshold.json"), "w") as f:
        json.dump(raw_bundle["metrics"], f, indent=2)

    with open(os.path.join(backend_dir, "roc_points.json"), "w") as f:
        json.dump(raw_bundle["roc_data"], f, indent=2)

    with open(os.path.join(backend_dir, "det_points.json"), "w") as f:
        json.dump(raw_bundle["det_data"], f, indent=2)

    with open(os.path.join(backend_dir, "mindcf.json"), "w") as f:
        json.dump(raw_bundle["mindcf_res"], f, indent=2)

    with open(os.path.join(backend_dir, "score_dist.json"), "w") as f:
        json.dump(raw_bundle["score_dist_res"], f, indent=2)

    with open(os.path.join(backend_dir, "calibration.json"), "w") as f:
        json.dump(raw_bundle["calib_res"], f, indent=2)
        
    print(f"Results saved to {backend_dir}")
    print(f"EER: {raw_bundle['eer']:.4f}")
    print(f"Threshold: {raw_bundle['eer_threshold']:.4f}")

def main():
    parser = argparse.ArgumentParser()
    # Default to configs/evaluate.yaml
    parser.add_argument("--config", "-c", default="configs/evaluate.yaml", help="Path to config yaml file")
    parser.add_argument("--model", help="Model path")
    parser.add_argument("--feature_dir", help="Feature directory")
    parser.add_argument("--out_dir", help="Output directory")
    parser.add_argument("--max_pairs", type=int, help="Max pairs for EER")
    parser.add_argument("--noise_dir", help="Noise directory for augmentation")
    parser.add_argument("--score_norm", choices=["none", "znorm", "tnorm", "snorm"], default="none")
    parser.add_argument("--cohort_speakers", type=int)
    parser.add_argument("--cohort_utts_per_spk", type=int)
    parser.add_argument("--cohort_seed", type=int)
    
    args = parser.parse_args()
    
    cfg = {}
    if args.config:
        if os.path.exists(args.config):
            cfg = load_config(args.config)
        else:
            print(f"Warning: Config {args.config} not found.")
            
    eval_args = EvalArgs(args, cfg)
    run_eval(eval_args)

# Alias for view_utils.py compatibility
run = run_eval

if __name__ == "__main__":
    main()
