import argparse
import os
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from python_speech_features import mfcc, delta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import PROCESSED_DIR, FEATURES_DIR

SAMPLE_RATE = 16000
N_MFCC = 13

def extract_mfcc(wav_path):
    y, sr = sf.read(wav_path)

    # 转单声道
    if len(y.shape) > 1:
        y = y.mean(axis=1)

    # 保证采样率 16k
    if sr != SAMPLE_RATE:
        raise ValueError(f"采样率不是16k: {wav_path}")

    # MFCC
    mfcc_feat = mfcc(
        y,
        samplerate=SAMPLE_RATE,
        numcep=N_MFCC,
        winlen=0.025,
        winstep=0.01,
        nfft=512
    )

    # 一阶差分
    d1 = delta(mfcc_feat, 2)
    # 二阶差分
    d2 = delta(d1, 2)

    feat = np.hstack([mfcc_feat, d1, d2])  # (frames, 39)
    return feat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_root", default=str(PROCESSED_DIR))
    parser.add_argument("--out_root", default=str(FEATURES_DIR))
    args = parser.parse_args()

    in_root = Path(args.in_root)
    out_root = Path(args.out_root)
    if not in_root.exists():
        raise FileNotFoundError(in_root)

    for user_dir in in_root.iterdir():
        if not user_dir.is_dir():
            continue
        wav_list = [w for w in user_dir.iterdir() if w.suffix.lower() == ".wav"]
        print(f"\n🎤 正在提取用户 {user_dir.name} ，共 {len(wav_list)} 条")
        for i, wav in enumerate(wav_list, 1):
            feat = extract_mfcc(str(wav))
            out_dir = out_root / user_dir.name
            os.makedirs(out_dir, exist_ok=True)
            out_path = out_dir / f"{wav.stem}.npy"
            np.save(out_path, feat)
            print(f"   [{i}/{len(wav_list)}] ✔ {wav.name}  shape={feat.shape}")


if __name__ == "__main__":
    main()
