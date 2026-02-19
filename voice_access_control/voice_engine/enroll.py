"""
Usage (from project root):
python -m voice_engine.enroll user_id path/to/1.wav path/to/2.wav ...

This will load model (models/ecapa_best.pth by default), extract embedding for each wav,
average them and save/update data/voiceprints/user_templates.npy
"""
import os
import numpy as np
import torch

from .ecapa_tdnn import LightECAPA
from .config import (
    MODEL_PATH,
    TEMPLATE_PATH,
    DEFAULT_N_MELS,
    FEATURE_TYPE_MFCC_DELTA,
    DEFAULT_DEVICE
)
from .features import (
    extract_feature_tensor,
    infer_feature_type_from_feat_dim,
    get_feature_dim
)


def load_model(model_path=MODEL_PATH, device=None, feature_type=None, n_mels=DEFAULT_N_MELS):
    if device is None:
        device = DEFAULT_DEVICE if torch.cuda.is_available() else "cpu"
    state = torch.load(model_path, map_location=device)
    if feature_type is None:
        w = state.get("layer1.conv.weight")
        if w is not None and w.ndim == 3:
            feat_dim_state = int(w.shape[1])
            feature_type = infer_feature_type_from_feat_dim(feat_dim_state, n_mels)
        else:
            feature_type = FEATURE_TYPE_MFCC_DELTA
    feat_dim = get_feature_dim(feature_type, n_mels)
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(device)
    model.load_state_dict(state, strict=False)
    model.eval()
    return model, device, feature_type


def extract_embedding(model, device, wav_path, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=DEFAULT_N_MELS):
    feat = extract_feature_tensor(wav_path, feature_type=feature_type, n_mels=n_mels, device=device)
    lengths = torch.tensor([feat.shape[2]], device=device)
    with torch.no_grad():
        emb = model(feat, lengths, return_embedding=True)
    emb = emb.detach().cpu().numpy()[0]
    return emb


def enroll(user_id, wav_paths, model_path=MODEL_PATH, template_path=TEMPLATE_PATH, feature_type=None, n_mels=DEFAULT_N_MELS):
    assert len(wav_paths) >= 1, "至少提供一条 wav 来注册"
    os.makedirs(os.path.dirname(template_path), exist_ok=True)

    model, device, feature_type = load_model(model_path, None, feature_type=feature_type, n_mels=n_mels)
    embs = []
    for p in wav_paths:
        if not os.path.exists(p):
            raise FileNotFoundError(p)
        print(f"  提取：{p}")
        e = extract_embedding(model, device, p, feature_type=feature_type, n_mels=n_mels)
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
        print("用法: python -m voice_engine.enroll <user_id> <wav1> <wav2> ...")
        sys.exit(1)
    user = sys.argv[1]
    wavs = sys.argv[2:]
    enroll(user, wavs)
