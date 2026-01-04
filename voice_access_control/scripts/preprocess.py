import librosa
import numpy as np
import os
import soundfile as sf
import matplotlib.pyplot as plt

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
    """
    幅度归一化
    """
    return y / np.max(np.abs(y))

def preprocess_wav(in_path, out_path):
    y, sr = librosa.load(in_path, sr=SAMPLE_RATE)
    y = remove_silence(y)
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
if __name__ == "__main__":
    #处理声音
    in_root = "data/raw"
    out_root = "data/processed"

    for user in os.listdir(in_root):
        user_dir = os.path.join(in_root, user)
        if not os.path.isdir(user_dir):
            continue

        for wav in os.listdir(user_dir):
            if not wav.endswith(".wav"):
                continue

            in_path = os.path.join(user_dir, wav)
            out_path = os.path.join(out_root, user, wav)

            preprocess_wav(in_path, out_path)
            print(f"✔ 处理完成: {out_path}")

    #波形可视化
    test_wav = "data/raw/user01/001.wav"
    y_raw, _ = librosa.load(test_wav, sr=SAMPLE_RATE)

    y_clean = remove_silence(y_raw)
    y_clean = pre_emphasis(y_clean)
    y_clean = normalize(y_clean)

    plot_wave(y_raw, "Raw Audio Waveform")
    plot_wave(y_clean, "Preprocessed Audio Waveform")