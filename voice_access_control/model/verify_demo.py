# model/verify_demo.py
import numpy as np
import torch
import os
from .ecapa_tdnn import LightECAPA
from .infer import load_templates, cosine_score
import soundfile as sf
from python_speech_features import mfcc, delta

def wav_to_feat(wav_path):
    y, sr = sf.read(wav_path)
    if len(y.shape) > 1:
        y = y.mean(axis=1)
    assert sr == 16000
    m = mfcc(y, samplerate=sr, numcep=13, winlen=0.025, winstep=0.01, nfft=512)
    d1 = delta(m, 2)
    d2 = delta(d1, 2)
    feat = np.hstack([m, d1, d2])
    return torch.from_numpy(feat.T).unsqueeze(0).float()  # (1, C, T)

def verify(wav_path, model_path="models/ecapa_best.pth", threshold=0.75):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = LightECAPA(feat_dim=39, emb_dim=192, n_speakers=None).to(device)
    state = torch.load(model_path, map_location=device)
    model.load_state_dict(state, strict=False)
    model.eval()
    templates = load_templates("data/voiceprints/templates.npy")
    feat = wav_to_feat(wav_path).to(device)
    lengths = torch.tensor([feat.shape[2]], device=device)
    with torch.no_grad():  # ⭐ 推理阶段关闭梯度
        emb = model(feat, lengths, return_embedding=True)

    emb = emb.detach().cpu().numpy()[0]
    # compare against each template
    best_spk, best_score = None, -1.0
    for spk, tmpl in templates.items():
        s = cosine_score(emb, tmpl)
        if s > best_score:
            best_score = s
            best_spk = spk
    result = "ACCEPT" if best_score >= threshold else "REJECT"
    print(f"Best match: {best_spk} score={best_score:.4f} => {result}")
    return best_spk, best_score, result

if __name__ == "__main__":
    import sys
    wav = sys.argv[1]
    verify(wav)
