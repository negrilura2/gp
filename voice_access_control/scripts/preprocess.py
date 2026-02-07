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
if __name__ == "__main__":
    #处理声音
    in_root = "data/raw"
    out_root = "data/processed"

    for user in os.listdir(in_root):
        user_dir = os.path.join(in_root, user)
        if not os.path.isdir(user_dir):
            continue

        wav_list = [w for w in os.listdir(user_dir) if w.endswith(".wav")]
        print(f"\n🎤 正在处理用户 {user} ，共 {len(wav_list)} 条音频")

        for i, wav in enumerate(wav_list, 1):
            in_path = os.path.join(user_dir, wav)
            out_path = os.path.join(out_root, user, wav)

            preprocess_wav(in_path, out_path)
            print(f"   [{i}/{len(wav_list)}] ✔ {wav}")

    #波形可视化
    # test_wav = "data/raw/user01/001.wav"
    # y_raw, _ = librosa.load(test_wav, sr=SAMPLE_RATE)
    #
    # y_clean = remove_silence(y_raw)
    # y_clean = pre_emphasis(y_clean)
    # y_clean = normalize(y_clean)
    #
    # plot_wave(y_raw, "Raw Audio Waveform")
    # plot_wave(y_clean, "Preprocessed Audio Waveform")