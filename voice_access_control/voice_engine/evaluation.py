import torch
import numpy as np
from torch.utils.data import DataLoader, Subset
from .dataset import SpeakerDataset, pad_collate
import os

def extract_all_embeddings(model, device, feature_dir, batch_size=32, num_workers=0, mode='feature', augmentor=None):
    """
    Extract embeddings for an entire dataset directory.
    
    Returns:
        tuple: (embeddings, labels, spk2idx)
    """
    ds = SpeakerDataset(feature_dir, mode=mode, augmentor=augmentor)
    # Ensure num_workers is safe (0 on Windows sometimes avoids issues, or stick to low number)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, collate_fn=pad_collate, num_workers=num_workers)
    
    model.eval()
    embs = []
    all_labels = []
    
    with torch.no_grad():
        for feats, lengths, lbs in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            embs.append(emb.cpu().numpy())
            all_labels.append(lbs.numpy())
            
    if not embs:
        return np.array([]), np.array([]), ds.spk2idx
        
    embs = np.vstack(embs)
    all_labels = np.hstack(all_labels)
    return embs, all_labels, ds.spk2idx

def build_templates(model, feature_dir, device, batch_size=32, max_speakers=0, max_utts_per_spk=0, seed=42):
    """
    Build user templates (mean embeddings) from a dataset.
    Useful for testing enrollment scenarios.
    """
    ds = SpeakerDataset(feature_dir)
    spk2idx = ds.spk2idx
    
    # Filter speakers
    allowed_spk = None
    if max_speakers and max_speakers > 0 and len(spk2idx) > max_speakers:
        rng = np.random.RandomState(seed)
        all_spk = list(spk2idx.values())
        idx_sel = rng.choice(len(all_spk), size=max_speakers, replace=False)
        allowed_ids = set(all_spk[i] for i in idx_sel)
        allowed_spk = allowed_ids
        
    # Filter utterances per speaker
    use_limit_utt = max_utts_per_spk and max_utts_per_spk > 0
    utt_counter = {}
    indices = []
    
    for i, (_, label) in enumerate(ds.samples):
        if allowed_spk is not None and label not in allowed_spk:
            continue
        if use_limit_utt:
            cnt = utt_counter.get(label, 0)
            if cnt >= max_utts_per_spk:
                continue
            utt_counter[label] = cnt + 1
        indices.append(i)
    
    subset = Subset(ds, indices) if indices else ds
    loader = DataLoader(subset, batch_size=batch_size, shuffle=False, collate_fn=pad_collate)
    
    model.eval()
    emb_by_spk = {}
    
    with torch.no_grad():
        for feats, lengths, labels in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            emb = emb.cpu().numpy()
            labels = labels.numpy()
            
            for e, l in zip(emb, labels):
                if l not in emb_by_spk:
                    emb_by_spk[l] = []
                emb_by_spk[l].append(e)
                
    # Average
    templates = {}
    for l, embs_list in emb_by_spk.items():
        templates[l] = np.mean(embs_list, axis=0)
        
    return templates
