# model/enroll.py
"""
Usage (from project root):
python -m model.enroll user_id path/to/1.wav path/to/2.wav ...

This will load model (models/ecapa_best.pth by default), extract embedding for each wav,
average them and save/update data/voiceprints/user_templates.npy
"""
import os
import numpy as np
import torch
import soundfile as sf
import librosa

from .ecapa_tdnn import LightECAPA
from python_speech_features import mfcc, delta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODEL_PATH = os.path.join(ROOT, "models", "ecapa_best.pth")
TEMPLATE_PATH = os.path.join(ROOT, "data", "voiceprints", "user_templates.npy")
SAMPLE_RATE = 16000
N_MFCC = 13


def pre_emphasis(y, coeff=0.97):
    return np.append(y[0], y[1:] - coeff * y[:-1])


def normalize(y):
    max_val = np.max(np.abs(y))
    if max_val < 1e-6:
        return y
    return y / max_val


def preprocess_wave(y, sr):
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != SAMPLE_RATE:
        y = librosa.resample(y, orig_sr=sr, target_sr=SAMPLE_RATE)
        sr = SAMPLE_RATE
    y = pre_emphasis(y)
    y = normalize(y)
    return y, sr


def wav_to_feat_tensor(wav_path):
    y, sr = sf.read(wav_path)
    if len(y) == 0:
        raise RuntimeError(f"音频文件为空: {wav_path}")
    y, sr = preprocess_wave(y, sr)
    m = mfcc(y, samplerate=sr, numcep=N_MFCC, winlen=0.025, winstep=0.01, nfft=512)
    d1 = delta(m, 2)
    d2 = delta(d1, 2)
    feat = np.hstack([m, d1, d2])
    return torch.from_numpy(feat.T).unsqueeze(0).float()


def load_model(model_path=MODEL_PATH, device=None):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = LightECAPA(feat_dim=39, emb_dim=192, n_speakers=None).to(device)
    state = torch.load(model_path, map_location=device)
    model.load_state_dict(state, strict=False)
    model.eval()
    return model, device


def extract_embedding(model, device, wav_path):
    feat = wav_to_feat_tensor(wav_path).to(device)
    lengths = torch.tensor([feat.shape[2]], device=device)
    with torch.no_grad():
        emb = model(feat, lengths, return_embedding=True)
    emb = emb.detach().cpu().numpy()[0]
    return emb


def enroll(user_id, wav_paths, model_path=MODEL_PATH, template_path=TEMPLATE_PATH):
    assert len(wav_paths) >= 1, "至少提供一条 wav 来注册"
    os.makedirs(os.path.dirname(template_path), exist_ok=True)

    model, device = load_model(model_path, None)
    embs = []
    for p in wav_paths:
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        print(f"  提取：{p}")
        e = extract_embedding(model, device, p)
        embs.append(e)

    user_template = np.mean(np.stack(embs, axis=0), axis=0)

    # load existing templates
    if os.path.exists(template_path):
        templates = np.load(template_path, allow_pickle=True).item()
    else:
        templates = {}

    templates[user_id] = user_template
    np.save(template_path, templates)
    print(f"✅ 注册完成：{user_id}，模板已保存到 {template_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python -m model.enroll <user_id> <wav1> <wav2> ...")
        sys.exit(1)
    user = sys.argv[1]
    wavs = sys.argv[2:]
    enroll(user, wavs)
