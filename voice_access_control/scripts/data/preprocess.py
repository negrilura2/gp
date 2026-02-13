import argparse
import os
import sys
from pathlib import Path
import librosa
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import RAW_DIR, PROCESSED_DIR

SAMPLE_RATE = 16000

def remove_silence(y, top_db=25):
    """
    静音切除
    """
    intervals = librosa.effects.split(y, top_db=top_db)
    if len(intervals) == 0:
        return y
    return np.concatenate([y[start:end] for start, end in intervals])

def pre_emphasis(y, coeff=0.97):
    """
    预加重
    """
    return np.append(y[0], y[1:] - coeff * y[:-1])

def normalize(y):
    max_val = np.max(np.abs(y))
    if max_val < 1e-6:
        return y
    return y / max_val


def preprocess_wav(in_path, out_path):
    # ✅ 用 soundfile 读音频（非常快且稳定）
    y, sr = sf.read(in_path)

    # 如果是双声道 → 转单声道
    if len(y.shape) > 1:
        y = y.mean(axis=1)

    # 重采样到 16k
    if sr != SAMPLE_RATE:
        y = librosa.resample(y, orig_sr=sr, target_sr=SAMPLE_RATE)

    # 预加重 + 归一化
    y = pre_emphasis(y)
    y = normalize(y)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sf.write(out_path, y, SAMPLE_RATE)

def plot_wave(y, title):
    plt.figure(figsize=(10, 3))
    plt.plot(y)
    plt.title(title)
    plt.xlabel("Samples")
    plt.ylabel("Amplitude")
    plt.tight_layout()
    plt.show()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_root", default=str(RAW_DIR))
    parser.add_argument("--out_root", default=str(PROCESSED_DIR))
    args = parser.parse_args()

    in_root = Path(args.in_root)
    out_root = Path(args.out_root)
    if not in_root.exists():
        raise FileNotFoundError(in_root)

    for user_dir in in_root.iterdir():
        if not user_dir.is_dir():
            continue
        wav_list = [w for w in user_dir.iterdir() if w.suffix.lower() == ".wav"]
        print(f"\n🎤 正在处理用户 {user_dir.name} ，共 {len(wav_list)} 条音频")
        for i, wav in enumerate(wav_list, 1):
            out_path = out_root / user_dir.name / wav.name
            preprocess_wav(str(wav), str(out_path))
            print(f"   [{i}/{len(wav_list)}] ✔ {wav.name}")


if __name__ == "__main__":
    main()
