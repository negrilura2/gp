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
from voice_engine.ecapa_tdnn import LightECAPA
from voice_engine.dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader, Subset
from voice_engine.config import (
    SAMPLE_RATE,
    DEFAULT_N_MELS,
    FEATURE_TYPE_MFCC,
    FEATURE_TYPE_MFCC_DELTA,
    FEATURE_TYPE_LOGMEL,
    VALID_FEATURE_TYPES
)
from voice_engine.features import extract_feature_from_signal, load_and_resample
from voice_engine.augmentation import add_noise
from voice_engine.evaluation import build_templates
from voice_engine.config import SAMPLE_RATE
import soundfile as sf
import librosa
import scipy.signal

def extract_feature(y, sr, feature_type="mfcc", n_mels=40):
    return extract_feature_from_signal(y, sr, feature_type=feature_type, n_mels=n_mels, normalize=False)

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
            feat = extract_feature(y, sr, feature_type, n_mels=n_mels)
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", default="models/ecapa_best.pth")
    parser.add_argument("--feature_dir", default=str(FEATURES_DIR))
    parser.add_argument("--processed_dir", default=str(PROCESSED_DIR))
    parser.add_argument("--out_dir", default=str(REPORTS_DIR))
    parser.add_argument("--feature_type", choices=["mfcc", "mfcc_delta", "logmel"], default="mfcc_delta")
    parser.add_argument("--n_mels", type=int, default=40)
    parser.add_argument("--snr_list", default="clean,20,10")
    parser.add_argument("--noise_wav", default="")
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max_speakers", type=int, default=10)
    parser.add_argument("--max_utts_per_spk", type=int, default=3)
    args = parser.parse_args()

    if str(args.device).lower().startswith("cuda"):
        if not torch.cuda.is_available():
            print("WARNING: CUDA not available, switching to CPU")
            args.device = "cpu"
        else:
            try:
                # Try to allocate a small tensor to check memory
                t = torch.zeros(1).to(args.device)
                del t
                torch.cuda.empty_cache()
            except RuntimeError as e:
                print(f"WARNING: CUDA memory check failed ({e}), switching to CPU")
                args.device = "cpu"

    os.makedirs(args.out_dir, exist_ok=True)
    ds = SpeakerDataset(args.feature_dir)
    if len(ds) == 0:
        raise ValueError("feature_dir 内没有可用特征文件")
    sample_feat, _ = ds[0]
    feat_dim = int(sample_feat.shape[0])
    n_spk = len(ds.spk2idx)
    
    print(f"DEBUG: Initializing model with feat_dim={feat_dim}, n_spk={n_spk}, device={args.device}")
    try:
        model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=n_spk).to(args.device)
    except RuntimeError as e:
        if "out of memory" in str(e):
            print("ERROR: GPU OOM during model init. Switching to CPU.")
            args.device = "cpu"
            torch.cuda.empty_cache()
            model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=n_spk).to(args.device)
        else:
            raise
    
    print(f"DEBUG: Loading model state from {args.model_path}")
    state = torch.load(args.model_path, map_location=args.device)
    model.load_state_dict(state, strict=False)
    
    # Enable memory optimization
    if args.device == "cuda":
        torch.backends.cudnn.benchmark = True
    
    print("DEBUG: Starting build_templates...")
    try:
        templates, spk2idx = build_templates(
            model,
            args.feature_dir,
            args.device,
            batch_size=args.batch_size,
            max_speakers=args.max_speakers,
            max_utts_per_spk=args.max_utts_per_spk,
            seed=args.seed,
        )
    except RuntimeError as e:
        if "out of memory" in str(e):
             print("ERROR: GPU OOM during build_templates. Reducing batch size and retrying...")
             torch.cuda.empty_cache()
             templates, spk2idx = build_templates(
                model,
                args.feature_dir,
                args.device,
                batch_size=max(1, args.batch_size // 2), # Reduce batch size
                max_speakers=args.max_speakers,
                max_utts_per_spk=args.max_utts_per_spk,
                seed=args.seed,
            )
        else:
            raise

    print(f"DEBUG: build_templates finished. Generated {len(templates)} templates.")

    noise_y = None
    noise_tag = "white"
    if args.noise_wav:
        print(f"DEBUG: Checking noise file: {args.noise_wav}")
        if not os.path.isfile(args.noise_wav):
            print(f"DEBUG: Noise file not found: {args.noise_wav}")
            raise FileNotFoundError(args.noise_wav)
        
        print(f"DEBUG: Reading noise file: {args.noise_wav}")
        # 使用统一的 load_and_resample (如果需要的话，但这里 noise 处理比较特殊，暂时保留部分逻辑)
        # 不过为了减少 scipy.signal.resample 的重复，可以尝试复用 features.py 中的逻辑
        # 但 features.py 主要针对语音，这里是噪声，且后续有归一化逻辑
        # 考虑到噪声文件处理也可能 hang，最好也用 scipy.signal.resample (原代码已用)
        # 暂时保持原逻辑，因为噪声处理比较特殊 (归一化方式不同)
        noise_y, sr_n = sf.read(args.noise_wav)
        print(f"DEBUG: Noise file read. Shape: {noise_y.shape}, SR: {sr_n}")
        
        if len(noise_y.shape) > 1:
            noise_y = noise_y.mean(axis=1)
        if sr_n != SAMPLE_RATE:
            print(f"DEBUG: Resampling noise from {sr_n} to {SAMPLE_RATE}")
            try:
                # 显式使用 scipy.signal.resample 以避免 librosa 问题
                import scipy.signal
                num_n = int(len(noise_y) * SAMPLE_RATE / sr_n)
                noise_y = scipy.signal.resample(noise_y, num_n)
                print(f"DEBUG: Resampling done. New shape: {noise_y.shape}")
            except Exception as e:
                print(f"ERROR: Noise resampling failed: {e}")
                raise

        max_len = SAMPLE_RATE * 30
        if len(noise_y) > max_len:
            noise_y = noise_y[:max_len]
        noise_y = noise_y.astype(np.float32)
        noise_y = noise_y - np.mean(noise_y)
        noise_y = noise_y / (np.std(noise_y) + 1e-12)
        noise_tag = os.path.splitext(os.path.basename(args.noise_wav))[0]
    else:
        print("DEBUG: No noise file provided. Using white noise if needed.")

    snr_items = [s.strip() for s in args.snr_list.split(",") if s.strip()]
    levels = []
    accs = []
    template_ids = set(templates.keys())
    spk_subset = {spk: idx for spk, idx in spk2idx.items() if idx in template_ids}
    
    print(f"DEBUG: Evaluating {len(snr_items)} SNR levels on {len(spk_subset)} speakers.")

    for s in snr_items:
        if s.lower() == "clean":
            snr = None
            label = "clean"
        else:
            snr = float(s)
            label = f"{snr:g}dB"
        print(f"Evaluating noise level: {label}  (speakers={len(spk_subset)}, max_utts_per_spk={args.max_utts_per_spk})")
        
        try:
            acc = evaluate_noise(
                model,
                templates,
                spk_subset,
                args.processed_dir,
                args.feature_type,
                snr,
                args.device,
                args.n_mels,
                args.seed,
                noise_y,
                max_utts_per_spk=args.max_utts_per_spk,
            )
            print(f"DEBUG: Accuracy for {label}: {acc}")
            levels.append(label)
            accs.append(acc)
        except Exception as e:
            print(f"ERROR: Failed evaluating {label}: {e}")
            import traceback
            traceback.print_exc()

    tag = args.feature_type
    
    # Update paths to match new directory structure
    json_dir = os.path.join(args.out_dir, "archive", "noise_tests")
    plot_dir = os.path.join(args.out_dir, "archive", "plots", "noise")
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(plot_dir, exist_ok=True)

    out_json = os.path.join(json_dir, f"noise_robustness_{tag}_{noise_tag}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"levels": levels, "accuracy": accs}, f, ensure_ascii=False, indent=2)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return

    out_png = os.path.join(plot_dir, f"noise_robustness_{tag}_{noise_tag}.png")
    plt.figure(figsize=(7, 4))
    plt.plot(levels, accs, marker="o")
    plt.xlabel("Noise Level")
    plt.ylabel("Accuracy")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

if __name__ == "__main__":
    main()
