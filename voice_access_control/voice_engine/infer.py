import os
import numpy as np
import torch
from .ecapa_tdnn import LightECAPA
from .dataset import SpeakerDataset, pad_collate
from torch.utils.data import DataLoader

def extract_embeddings(model, feature_root, device):
    ds = SpeakerDataset(feature_root)
    loader = DataLoader(ds, batch_size=32, shuffle=False, collate_fn=pad_collate)
    model.eval()
    emb_dict = {}   # spk -> list of embeddings
    with torch.no_grad():
        for feats, lengths, labels in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)  # (B, emb_dim)
            emb = emb.cpu().numpy()
            labels = labels.numpy()
            for e, l in zip(emb, labels):
                # get speaker name from dataset mapping
                spk = list(ds.spk2idx.keys())[list(ds.spk2idx.values()).index(int(l))]  # inefficient but fine
                emb_dict.setdefault(spk, []).append(e)
    # average per speaker
    templates = {}
    for spk, embs in emb_dict.items():
        templates[spk] = np.mean(np.stack(embs, axis=0), axis=0)
    return templates

def save_templates(templates, out_path="data/voiceprints/user_templates.npy"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    np.save(out_path, templates)
    print("Saved templates:", out_path)

def load_templates(path="data/voiceprints/user_templates.npy"):
    return np.load(path, allow_pickle=True).item()

def cosine_score(a, b):
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    s = float(np.dot(a, b))
    if s > 1.0:
        s = 1.0
    elif s < -1.0:
        s = -1.0
    return s

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", default="models/ecapa_best.pth")
    parser.add_argument("--feature_dir", default="data/features")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    device = args.device
    ds = SpeakerDataset(args.feature_dir)
    n_spk = len(ds.spk2idx)
    sample_feat, _ = ds[0]
    feat_dim = int(sample_feat.shape[0])
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(device)
    state = torch.load(args.model_path, map_location=device)
    # if saved with classifier, state may contain classifier keys (ok to load)
    model.load_state_dict(state, strict=False)

    templates = extract_embeddings(model, args.feature_dir, device)
    save_templates(templates)
    # sample verification: compare first two templates
    keys = list(templates.keys())
    if len(keys) >= 2:
        s = cosine_score(templates[keys[0]], templates[keys[1]])
        print("Sample cos between", keys[0], keys[1], s)
