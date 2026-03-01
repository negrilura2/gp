import argparse
import os
import sys
import json
import numpy as np
import torch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import PROCESSED_DIR, FEATURES_DIR, REPORTS_DIR
from voice_engine.core.ecapa_tdnn import LightECAPA
from voice_engine.core.dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader, Subset
from voice_engine.config import (
    SAMPLE_RATE,
    DEFAULT_N_MELS,
    EMBEDDING_DIM,
    FEATURE_TYPE_MFCC_DELTA,
    FEATURE_TYPE_LOGMEL,
    VALID_FEATURE_TYPES
)
from voice_engine.core.dataset import (
    extract_feature_from_signal,
    load_and_resample,
    add_noise
)
from voice_engine.core.metrics import build_templates
from voice_engine.config import SAMPLE_RATE
import soundfile as sf
import scipy.signal

def evaluate_noise(model, templates, spk2idx, processed_root, feature_type, snr_db, device, n_mels, seed, noise_y, max_utts_per_spk=5):
    rng = np.random.RandomState(seed)
    total = 0
    correct = 0
    for spk, idx in spk2idx.items():
        spk_dir = os.path.join(processed_root, spk)
        if not os.path.isdir(spk_dir):
            continue
        utt_count = 0
        for name in os.listdir(spk_dir):
            if not name.lower().endswith(".wav"):
                continue
            wav_path = os.path.join(spk_dir, name)
            y, sr = sf.read(wav_path)
            y = add_noise(y, snr_db, rng, noise_y=noise_y)
            feat = extract_feature_from_signal(y, sr, feature_type=feature_type, n_mels=n_mels, normalize=False)
            feat = torch.from_numpy(feat).float().transpose(0, 1).unsqueeze(0).to(device)
            lengths = torch.tensor([feat.shape[2]], device=device)
            with torch.no_grad():
                emb = model(feat, lengths, return_embedding=True).cpu().numpy()[0]
            emb = emb / (np.linalg.norm(emb) + 1e-9)
            scores = {k: float(np.dot(emb, v)) for k, v in templates.items()}
            pred = max(scores.items(), key=lambda x: x[1])[0]
            total += 1
            if pred == idx:
                correct += 1
            utt_count += 1
            if utt_count >= max_utts_per_spk:
                break
    if total == 0:
        return 0.0
    return correct / total

import yaml

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", help="Path to config yaml file")
    parser.add_argument("--model_path", default=None)
    parser.add_argument("--feature_dir", default=None)
    parser.add_argument("--processed_dir", default=None)
    parser.add_argument("--out_dir", default=None)
    parser.add_argument("--feature_type", choices=["mfcc_delta", "logmel"], default=None)
    parser.add_argument("--n_mels", type=int, default=None)
    parser.add_argument("--snr_list", default=None)
    parser.add_argument("--noise_wav", default=None)
    parser.add_argument("--batch_size", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max_speakers", type=int, default=None)
    parser.add_argument("--max_utts_per_spk", type=int, default=None)
    args = parser.parse_args()

    cfg = {}
    if args.config:
        cfg = load_config(args.config)
        print(f"Loading config from {args.config}")

    # Priority: CLI > Config > Default
    model_path = args.model_path or cfg.get("model", {}).get("path") or "checkpoints/ecapa_best.pth"
    feature_dir = args.feature_dir or cfg.get("dataset", {}).get("feature_dir") or str(FEATURES_DIR)
    processed_dir = args.processed_dir or cfg.get("dataset", {}).get("processed_dir") or str(PROCESSED_DIR)
    out_dir = args.out_dir or cfg.get("analysis", {}).get("out_dir") or str(REPORTS_DIR)
    
    analysis_cfg = cfg.get("analysis", {})
    noise_cfg = analysis_cfg.get("noise", {})
    
    feature_type = args.feature_type or noise_cfg.get("feature_type", "mfcc_delta")
    n_mels = args.n_mels or noise_cfg.get("n_mels", DEFAULT_N_MELS)
    
    # snr_list handling: config might be list, cli is string
    snr_val = args.snr_list or noise_cfg.get("snr_list", "clean,20,10")
    if isinstance(snr_val, list):
        snr_list = snr_val
    else:
        snr_list = str(snr_val).split(",")
    
    noise_wav = args.noise_wav or noise_cfg.get("noise_wav", "")
    batch_size = args.batch_size or analysis_cfg.get("batch_size", 32)
    device = args.device or analysis_cfg.get("device", "cuda" if torch.cuda.is_available() else "cpu")
    seed = args.seed or analysis_cfg.get("seed", 42)
    max_speakers = args.max_speakers or noise_cfg.get("max_speakers", 10)
    max_utts_per_spk = args.max_utts_per_spk or noise_cfg.get("max_utts_per_spk", 3)


    if str(device).lower().startswith("cuda"):
        if not torch.cuda.is_available():
            print("WARNING: CUDA not available, switching to CPU")
            device = "cpu"
        else:
            try:
                # Try to allocate a small tensor to check memory
                t = torch.zeros(1).to(device)
                del t
                torch.cuda.empty_cache()
            except RuntimeError as e:
                print(f"WARNING: CUDA memory check failed ({e}), switching to CPU")
                device = "cpu"

    os.makedirs(out_dir, exist_ok=True)
    if os.path.isdir(feature_dir):
        feature_type_names = {"mfcc_delta", "logmel"}
        base_name = os.path.basename(os.path.normpath(feature_dir))
        candidate = os.path.join(feature_dir, feature_type)
        if base_name not in feature_type_names and os.path.isdir(candidate):
            feature_dir = candidate
    ds = SpeakerDataset(feature_dir)
    if len(ds) == 0:
        raise ValueError("feature_dir 内没有可用特征文件")
    sample_feat, _ = ds[0]
    feat_dim = int(sample_feat.shape[0])
    n_spk = len(ds.spk2idx)
    
    print(f"DEBUG: Initializing model with feat_dim={feat_dim}, n_spk={n_spk}, device={device}")
    try:
        model = LightECAPA(feat_dim=feat_dim, emb_dim=EMBEDDING_DIM, n_speakers=n_spk).to(device)
    except RuntimeError as e:
        if "out of memory" in str(e):
            print("ERROR: GPU OOM during model init. Switching to CPU.")
            device = "cpu"
            torch.cuda.empty_cache()
            model = LightECAPA(feat_dim=feat_dim, emb_dim=EMBEDDING_DIM, n_speakers=n_spk).to(device)
        else:
            raise
    
    print(f"DEBUG: Loading model state from {model_path}")
    state = torch.load(model_path, map_location=device)
    model.load_state_dict(state, strict=False)
    
    # Enable memory optimization
    if device == "cuda":
        torch.backends.cudnn.benchmark = True
    
    print("DEBUG: Starting build_templates...")
    try:
        templates_result = build_templates(
            model,
            feature_dir,
            device,
            batch_size=batch_size,
            max_speakers=max_speakers,
            max_utts_per_spk=max_utts_per_spk,
            seed=seed,
        )

        if isinstance(templates_result, tuple):
            if len(templates_result) >= 2:
                templates, spk2idx = templates_result[0], templates_result[1]
            else:
                templates, spk2idx = templates_result[0], ds.spk2idx
        else:
            templates, spk2idx = templates_result, ds.spk2idx
    except RuntimeError as e:
        if "out of memory" in str(e):
            print("ERROR: GPU OOM during build_templates. Reducing batch size and retrying...")
            torch.cuda.empty_cache()
            templates_result = build_templates(
                model,
                args.feature_dir,
                args.device,
                batch_size=max(1, args.batch_size // 2), # Reduce batch size
                max_speakers=args.max_speakers,
                max_utts_per_spk=args.max_utts_per_spk,
                seed=args.seed,
            )
            if isinstance(templates_result, tuple):
                if len(templates_result) >= 2:
                    templates, spk2idx = templates_result[0], templates_result[1]
                else:
                    templates, spk2idx = templates_result[0], ds.spk2idx
            else:
                templates, spk2idx = templates_result, ds.spk2idx
        else:
            raise

    print(f"DEBUG: build_templates finished. Generated {len(templates)} templates.")

    noise_y = None
    noise_tag = "white"
    if noise_wav:
        print(f"DEBUG: Checking noise file: {noise_wav}")
        if not os.path.isfile(noise_wav):
            print(f"DEBUG: Noise file not found: {noise_wav}")
            raise FileNotFoundError(noise_wav)
        
        print(f"DEBUG: Reading noise file: {noise_wav}")
        # 使用统一的 load_and_resample
        noise_y, sr_n = load_and_resample(noise_wav)
        print(f"DEBUG: Noise file read. Shape: {noise_y.shape}, SR: {sr_n}")
        
        noise_tag = os.path.splitext(os.path.basename(noise_wav))[0]
    
    print(f"DEBUG: Starting evaluation loops. SNR list: {snr_list}")
    
    results = {}
    
    # Clean baseline
    if "clean" in snr_list:
        print(f"\nEvaluating CLEAN...")
        acc = evaluate_noise(model, templates, spk2idx, processed_dir, feature_type, None, device, n_mels, seed, None, max_utts_per_spk)
        results["clean"] = acc
        print(f"Clean Acc: {acc:.4f}")
        
    for snr in snr_list:
        if str(snr) == "clean": continue
        snr_val = float(snr)
        print(f"\nEvaluating SNR={snr_val}db...")
        acc = evaluate_noise(model, templates, spk2idx, processed_dir, feature_type, snr_val, device, n_mels, seed, noise_y, max_utts_per_spk)
        results[f"{snr_val}db"] = acc
        print(f"SNR {snr_val}db Acc: {acc:.4f}")

    # Plot
    model_name = os.path.splitext(os.path.basename(model_path))[0]
    out_png = os.path.join(out_dir, "plots", "noise", f"noise_robustness_{feature_type}_{noise_tag}_{model_name}.png")
    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    
    plt.figure(figsize=(8, 6))
    x_labels = [k for k in results.keys()]
    y_values = [v for v in results.values()]
    plt.plot(x_labels, y_values, marker='o', linestyle='-')
    plt.title(f"Noise Robustness ({noise_tag}) - {feature_type}")
    plt.xlabel("SNR (db)")
    plt.ylabel("Accuracy")
    plt.grid(True)
    plt.ylim(0, 1.05)
    for i, v in enumerate(y_values):
        plt.text(i, v + 0.01, f"{v:.2f}", ha='center')
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()
    print(f"Saved plot to {out_png}")

if __name__ == "__main__":
    main()
