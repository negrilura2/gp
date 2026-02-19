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
from voice_engine.config import SAMPLE_RATE
import soundfile as sf
import librosa
import scipy.signal

def extract_feature(y, sr, feature_type="mfcc", n_mels=40):
    # 使用统一的 features.extract_feature_from_signal
    # 注意: extract_feature_from_signal 返回 (T, dim)
    # 而 noise_robustness 中原来的逻辑也返回 (T, dim)
    # 所以直接调用即可
    return extract_feature_from_signal(y, sr, feature_type=feature_type, n_mels=n_mels, normalize=False)

def add_noise(y, snr_db, rng, noise_y=None):
    if snr_db is None:
        return y
    signal_power = np.mean(y ** 2)
    if signal_power <= 1e-12:
        return y
    snr_linear = 10 ** (snr_db / 10.0)
    noise_power = signal_power / snr_linear
    if noise_y is None:
        noise = rng.normal(0.0, np.sqrt(noise_power), size=y.shape)
        return y + noise
    if len(noise_y) < len(y):
        rep = int(np.ceil(len(y) / len(noise_y)))
        src = np.tile(noise_y, rep)[: len(y)]
    else:
        start = rng.randint(0, len(noise_y) - len(y) + 1)
        src = noise_y[start : start + len(y)]
    noise = src * np.sqrt(noise_power)
    
    # Ensure no clipping if possible, or clip? Usually for SNR we just add.
    # But if we want to save or process, values > 1 might be an issue?
    # For feature extraction, float32 > 1 is fine usually.
    return y + noise

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
    
    print(f"DEBUG: Selected {len(indices)} samples for templates.")
    subset = Subset(ds, indices) if indices else ds
    loader = DataLoader(subset, batch_size=batch_size, shuffle=False, collate_fn=pad_collate)
    
    model.eval()
    emb_by_spk = {}
    print("DEBUG: Starting template inference loop...")
    with torch.no_grad():
        for batch_idx, (feats, lengths, labels) in enumerate(loader):
            if batch_idx % 10 == 0:
                print(f"DEBUG: Processing batch {batch_idx}")
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            emb = emb.cpu().numpy()
            labels = labels.numpy()
            for e, l in zip(emb, labels):
                lid = int(l)
                emb_by_spk.setdefault(lid, []).append(e)
    print("DEBUG: Template inference loop done.")
    templates = {}
    for spk, embs in emb_by_spk.items():
        arr = np.stack(embs, axis=0)
        avg = np.mean(arr, axis=0)
        avg = avg / (np.linalg.norm(avg) + 1e-9)
        templates[spk] = avg
    return templates, spk2idx

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
