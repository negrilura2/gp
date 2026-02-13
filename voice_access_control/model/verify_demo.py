# model/verify_demo.py
"""
声纹验证模块。
支持两种调用方式：
1. verify(wav_path) — 自动加载模型（命令行 / 脚本使用）
2. verify(wav_path, model=已加载模型, device=...) — 外部注入模型（API 单例模式）
"""
import numpy as np
import torch
import os
from .ecapa_tdnn import LightECAPA
from .infer import cosine_score
import soundfile as sf
from python_speech_features import mfcc, delta
from .enroll import SAMPLE_RATE, N_MFCC, pre_emphasis, normalize, preprocess_wave

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEMPLATE_PATH = os.path.join(ROOT, "data", "voiceprints", "user_templates.npy")


def load_templates(path=None):
    """加载声纹模板字典 {user_id: embedding}"""
    path = path or TEMPLATE_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"模板文件不存在: {path}，请先执行注册(enroll)")
    return np.load(path, allow_pickle=True).item()


def wav_to_feat(wav_path):
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"音频文件不存在: {wav_path}")
    y, sr = sf.read(wav_path)
    if len(y) == 0:
        raise ValueError(f"音频文件为空: {wav_path}")
    y, sr = preprocess_wave(y, sr)
    m = mfcc(y, samplerate=SAMPLE_RATE, numcep=N_MFCC, winlen=0.025, winstep=0.01, nfft=512)
    d1 = delta(m, 2)
    d2 = delta(d1, 2)
    feat = np.hstack([m, d1, d2])
    return torch.from_numpy(feat.T).unsqueeze(0).float()


def verify(wav_path, model_path="models/ecapa_best.pth", threshold=0.75,
           model=None, device=None, template_path=None):
    """
    声纹验证。

    参数：
        wav_path: 待验证音频路径
        model_path: 模型权重路径（当 model=None 时使用）
        threshold: 接受阈值
        model: 已加载的模型对象（用于 API 单例模式，避免重复加载）
        device: 设备（当 model 外部传入时需同时传入）
        template_path: 模板文件路径，默认使用 TEMPLATE_PATH

    返回：
        (best_spk, best_score, result)
    """
    # 加载模型（若未外部注入）
    if model is None:
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        model = LightECAPA(feat_dim=39, emb_dim=192, n_speakers=None).to(device)
        state = torch.load(model_path, map_location=device)
        model.load_state_dict(state, strict=False)
        model.eval()
    else:
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    # 加载模板
    templates = load_templates(template_path)

    # 提取 embedding
    feat = wav_to_feat(wav_path).to(device)
    lengths = torch.tensor([feat.shape[2]], device=device)
    with torch.no_grad():
        emb = model(feat, lengths, return_embedding=True)

    emb = emb.detach().cpu().numpy()[0]

    # 与每个模板比对
    best_spk, best_score = None, -1.0
    for spk, tmpl in templates.items():
        # 支持 multi-shot：tmpl 可能是单条 embedding 或 embedding 列表
        if isinstance(tmpl, np.ndarray) and tmpl.ndim == 1:
            s = cosine_score(emb, tmpl)
        elif isinstance(tmpl, (list, np.ndarray)):
            # 多条模板取最大相似度
            scores = [cosine_score(emb, t) for t in tmpl]
            s = max(scores)
        else:
            s = cosine_score(emb, tmpl)

        if s > best_score:
            best_score = s
            best_spk = spk

    result = "ACCEPT" if best_score >= threshold else "REJECT"
    print(f"Best match: {best_spk} score={best_score:.4f} => {result}")
    return best_spk, best_score, result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python -m model.verify_demo <wav_path> [--threshold 0.75]")
        sys.exit(1)
    wav = sys.argv[1]
    thr = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == "--threshold" else 0.75
    verify(wav, threshold=thr)
