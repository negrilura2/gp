import librosa
import numpy as np
import os

SAMPLE_RATE = 16000
N_MFCC = 13

def extract_mfcc(wav_path):
    y, sr = librosa.load(wav_path, sr=SAMPLE_RATE)

    mfcc = librosa.feature.mfcc(
        y=y,
        sr=sr,
        n_mfcc=N_MFCC,
        n_fft=int(0.025 * sr),
        hop_length=int(0.010 * sr)
    )

    delta = librosa.feature.delta(mfcc)
    delta2 = librosa.feature.delta(mfcc, order=2)

    mfcc_feat = np.vstack([mfcc, delta, delta2])
    return mfcc_feat.T  # (frames, 39)

if __name__ == "__main__":
    in_root = "data/processed"
    out_root = "data/features"

    for user in os.listdir(in_root):
        user_dir = os.path.join(in_root, user)
        if not os.path.isdir(user_dir):
            continue

        for wav in os.listdir(user_dir):
            if not wav.endswith(".wav"):
                continue

            wav_path = os.path.join(user_dir, wav)
            feat = extract_mfcc(wav_path)

            out_dir = os.path.join(out_root, user)
            os.makedirs(out_dir, exist_ok=True)

            out_path = os.path.join(out_dir, wav.replace(".wav", ".npy"))
            np.save(out_path, feat)

            print(f"✔ MFCC 保存完成: {out_path}, shape={feat.shape}")
