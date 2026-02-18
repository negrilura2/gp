import argparse
import os
import sys
import json
import numpy as np
import soundfile as sf
import librosa
import torch
import torch.nn.functional as F
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from python_speech_features import mfcc, delta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import PROCESSED_DIR, FEATURES_DIR, REPORTS_DIR
from model.ecapa_tdnn import LightECAPA
from model.dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader

SAMPLE_RATE = 16000

def extract_feature(y, sr, feature_type, n_mels=40):
    if len(y.shape) > 1:
        y = y.mean(axis=1)
    if sr != SAMPLE_RATE:
        y = librosa.resample(y, orig_sr=sr, target_sr=SAMPLE_RATE)
        sr = SAMPLE_RATE
    if feature_type == "logmel":
        mel = librosa.feature.melspectrogram(
            y=y,
            sr=SAMPLE_RATE,
            n_mels=n_mels,
            n_fft=512,
            hop_length=int(0.01 * SAMPLE_RATE),
            win_length=int(0.025 * SAMPLE_RATE),
            power=2.0,
        )
        logmel = librosa.power_to_db(mel, ref=np.max)
        return logmel.T
    m = mfcc(y, samplerate=sr, numcep=13, winlen=0.025, winstep=0.01, nfft=512)
    if feature_type == "mfcc":
        return m
    d1 = delta(m, 2)
    d2 = delta(d1, 2)
    return np.hstack([m, d1, d2])

def add_noise(y, snr_db, rng):
    if snr_db is None:
        return y
    signal_power = np.mean(y ** 2)
    if signal_power <= 1e-12:
        return y
    snr_linear = 10 ** (snr_db / 10.0)
    noise_power = signal_power / snr_linear
    noise = rng.normal(0.0, np.sqrt(noise_power), size=y.shape)
    return y + noise

def build_templates(model, feature_dir, device, batch_size=32):
    ds = SpeakerDataset(feature_dir)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, collate_fn=pad_collate)
    model.eval()
    emb_by_spk = {}
    with torch.no_grad():
        for feats, lengths, labels in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            emb = emb.cpu().numpy()
            labels = labels.numpy()
            for e, l in zip(emb, labels):
                emb_by_spk.setdefault(int(l), []).append(e)
    templates = {}
    for spk, embs in emb_by_spk.items():
        arr = np.stack(embs, axis=0)
        avg = np.mean(arr, axis=0)
        avg = avg / (np.linalg.norm(avg) + 1e-9)
        templates[spk] = avg
    return templates, ds.spk2idx

def evaluate_noise(model, templates, spk2idx, processed_root, feature_type, snr_db, device, n_mels, seed):
    rng = np.random.RandomState(seed)
    total = 0
    correct = 0
    for spk, idx in spk2idx.items():
        spk_dir = os.path.join(processed_root, spk)
        if not os.path.isdir(spk_dir):
            continue
        for name in os.listdir(spk_dir):
            if not name.lower().endswith(".wav"):
                continue
            wav_path = os.path.join(spk_dir, name)
            y, sr = sf.read(wav_path)
            y = add_noise(y, snr_db, rng)
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
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    ds = SpeakerDataset(args.feature_dir)
    if len(ds) == 0:
        raise ValueError("feature_dir 内没有可用特征文件")
    sample_feat, _ = ds[0]
    feat_dim = int(sample_feat.shape[0])
    n_spk = len(ds.spk2idx)
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=n_spk).to(args.device)
    state = torch.load(args.model_path, map_location=args.device)
    model.load_state_dict(state, strict=False)
    templates, spk2idx = build_templates(model, args.feature_dir, args.device, batch_size=args.batch_size)

    snr_items = [s.strip() for s in args.snr_list.split(",") if s.strip()]
    levels = []
    accs = []
    for s in snr_items:
        if s.lower() == "clean":
            snr = None
            label = "clean"
        else:
            snr = float(s)
            label = f"{snr:g}dB"
        acc = evaluate_noise(
            model,
            templates,
            spk2idx,
            args.processed_dir,
            args.feature_type,
            snr,
            args.device,
            args.n_mels,
            args.seed,
        )
        levels.append(label)
        accs.append(acc)

    tag = args.feature_type
    out_png = os.path.join(args.out_dir, f"noise_robustness_{tag}.png")
    plt.figure(figsize=(7, 4))
    plt.plot(levels, accs, marker="o")
    plt.xlabel("Noise Level")
    plt.ylabel("Accuracy")
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()

    out_json = os.path.join(args.out_dir, f"noise_robustness_{tag}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"levels": levels, "accuracy": accs}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
