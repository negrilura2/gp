import numpy as np
import os
import soundfile as sf
from python_speech_features import mfcc, delta

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


if __name__ == "__main__":
    in_root = "data/processed"
    out_root = "data/features"

    for user in os.listdir(in_root):
        user_dir = os.path.join(in_root, user)
        if not os.path.isdir(user_dir):
            continue

        wav_list = [w for w in os.listdir(user_dir) if w.endswith(".wav")]
        print(f"\n🎤 正在提取用户 {user} ，共 {len(wav_list)} 条")

        for i, wav in enumerate(wav_list, 1):
            wav_path = os.path.join(user_dir, wav)
            feat = extract_mfcc(wav_path)

            out_dir = os.path.join(out_root, user)
            os.makedirs(out_dir, exist_ok=True)

            out_path = os.path.join(out_dir, wav.replace(".wav", ".npy"))
            np.save(out_path, feat)

            print(f"   [{i}/{len(wav_list)}] ✔ {wav}  shape={feat.shape}")
