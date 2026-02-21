import argparse, os, time, json, csv, math
import numpy as np
import torch
from torch.utils.data import DataLoader
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve
from .dataset import SpeakerDataset, pad_collate
from .ecapa_tdnn import LightECAPA

class AAMSoftmaxLoss(nn.Module):
    def __init__(self, s=30.0, m=0.2):
        super().__init__()
        self.s = s
        self.m = m
        self.cos_m = math.cos(m)
        self.sin_m = math.sin(m)

    def forward(self, embeddings, labels, weight):
        emb = F.normalize(embeddings, p=2, dim=1)
        W = F.normalize(weight, p=2, dim=1)
        cosine = F.linear(emb, W)
        cosine = cosine.clamp(-1 + 1e-7, 1 - 1e-7)
        sine = torch.sqrt(1.0 - cosine * cosine)
        phi = cosine * self.cos_m - sine * self.sin_m
        one_hot = torch.zeros_like(cosine)
        one_hot.scatter_(1, labels.view(-1, 1), 1.0)
        logits = (one_hot * phi) + ((1.0 - one_hot) * cosine)
        logits = logits * self.s
        loss = F.cross_entropy(logits, labels)
        return loss, logits

def train_epoch(model, loader, opt, device, loss_type, loss_fn):
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    for batch_idx, (feats, lengths, labels) in enumerate(loader):
        feats = feats.to(device)         # (B, C, T)
        lengths = lengths.to(device)
        labels = labels.to(device)
        opt.zero_grad()
        if loss_type == "aam":
            emb = model(feats, lengths, return_embedding=True)
            loss, logits = loss_fn(emb, labels, model.classifier.weight)
        else:
            logits, _ = model(feats, lengths)
            loss = loss_fn(logits, labels)
        loss.backward()
        opt.step()
        total_loss += loss.item()
        preds = torch.argmax(logits, dim=1)
        total_correct += (preds == labels).sum().item()
        total_count += labels.numel()
    avg_loss = total_loss / (batch_idx + 1)
    acc = total_correct / total_count if total_count else 0.0
    return avg_loss, acc

def evaluate(model, loader, device, loss_type, loss_fn):
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    with torch.no_grad():
        for batch_idx, (feats, lengths, labels) in enumerate(loader):
            feats = feats.to(device)
            lengths = lengths.to(device)
            labels = labels.to(device)
            if loss_type == "aam":
                emb = model(feats, lengths, return_embedding=True)
                loss, logits = loss_fn(emb, labels, model.classifier.weight)
            else:
                logits, _ = model(feats, lengths)
                loss = loss_fn(logits, labels)
            total_loss += loss.item()
            preds = torch.argmax(logits, dim=1)
            total_correct += (preds == labels).sum().item()
            total_count += labels.numel()
    avg_loss = total_loss / (batch_idx + 1)
    acc = total_correct / total_count if total_count else 0.0
    return avg_loss, acc

def collect_embeddings(model, loader, device):
    model.eval()
    all_embs = []
    all_labels = []
    with torch.no_grad():
        for feats, lengths, labels in loader:
            feats = feats.to(device)
            lengths = lengths.to(device)
            emb = model(feats, lengths, return_embedding=True)
            all_embs.append(emb.cpu())
            all_labels.append(labels.cpu())
    if not all_embs:
        return None, None
    return torch.cat(all_embs, dim=0).numpy(), torch.cat(all_labels, dim=0).numpy()

def compute_eer_from_embeddings(embs, labels, max_pairs=20000, seed=42):
    if embs is None or labels is None or len(embs) < 2:
        return None
    rng = np.random.RandomState(seed)
    labels = labels.astype(int)
    norm = np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    embs = embs / norm
    spk_to_idx = {}
    for i, lb in enumerate(labels):
        spk_to_idx.setdefault(lb, []).append(i)
    spk_ids = list(spk_to_idx.keys())
    if len(spk_ids) < 2:
        return None
    same_pairs = []
    for idxs in spk_to_idx.values():
        if len(idxs) < 2:
            continue
        for i in range(len(idxs)):
            for j in range(i + 1, len(idxs)):
                same_pairs.append((idxs[i], idxs[j]))
    max_same = max_pairs // 2
    if len(same_pairs) > max_same:
        same_pairs = [same_pairs[i] for i in rng.choice(len(same_pairs), max_same, replace=False)]
    same_scores = [float(np.dot(embs[i], embs[j])) for i, j in same_pairs]
    max_diff = max_pairs - len(same_scores)
    diff_scores = []
    attempts = 0
    total = len(labels)
    while len(diff_scores) < max_diff and attempts < max_diff * 20:
        i = rng.randint(0, total)
        j = rng.randint(0, total)
        if labels[i] == labels[j]:
            attempts += 1
            continue
        diff_scores.append(float(np.dot(embs[i], embs[j])))
        attempts += 1
    if not same_scores or not diff_scores:
        return None
    y = np.array([1] * len(same_scores) + [0] * len(diff_scores))
    scores = np.array(same_scores + diff_scores)
    fpr, tpr, thresholds = roc_curve(y, scores, pos_label=1)
    fnr = 1 - tpr
    idx = np.argmin(np.abs(fpr - fnr))
    eer = (fpr[idx] + fnr[idx]) / 2.0
    return float(eer)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature_dir", default="data/features")
    parser.add_argument("--save_dir", default="models")
    parser.add_argument("--log_dir", default="reports")
    parser.add_argument("--model_name", default="ecapa_best.pth")
    parser.add_argument("--noise_dir", default=None)
    parser.add_argument("--feature_type", default="mfcc_delta")
    parser.add_argument("--n_mels", type=int, default=40)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--optimizer", choices=["adam", "adamw"], default="adam")
    parser.add_argument("--loss", choices=["ce", "aam"], default="ce")
    parser.add_argument("--aam_s", type=float, default=30.0)
    parser.add_argument("--aam_m", type=float, default=0.2)
    parser.add_argument("--eer_pairs", type=int, default=20000)
    parser.add_argument("--eer_interval", type=int, default=5)
    parser.add_argument("--feature_tag", default="default")
    parser.add_argument("--loader_workers", type=int, default=-1)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    # Level 4: Early Stopping 参数
    parser.add_argument("--early_stop", action="store_true", help="Enable early stopping")
    parser.add_argument("--patience", type=int, default=3, help="Early stopping patience")
    args = parser.parse_args()

    augmentor = None
    mode = 'feature'
    
    if args.noise_dir:
        from .augmentation import NoiseAugmentor
        augmentor = NoiseAugmentor(args.noise_dir)
        print(f"Noise Augmentation Enabled: {args.noise_dir}")
        # If noise_dir is set, switch to raw wav mode if feature_dir is still default
        if args.feature_dir == "data/features":
             print("Info: Switching data source to 'data/processed' for raw wav loading.")
             args.feature_dir = "data/processed"
        mode = 'raw'

    # Update paths to match new directory structure if using default names and NOT noise training
    # If noise training, user usually provides explicit save_dir or we use args.save_dir directly
    if args.save_dir == "models" and not args.noise_dir:
        args.save_dir = os.path.join("models", "archive", args.feature_tag)
    
    if args.log_dir == "reports" and not args.noise_dir:
        args.log_dir = os.path.join("reports", "metrics")

    os.makedirs(args.save_dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    
    print(f"Dataset Mode: {mode}, Root: {args.feature_dir}")
    ds = SpeakerDataset(
        args.feature_dir,
        mode=mode,
        augmentor=augmentor,
        feature_type=args.feature_type,
        n_mels=args.n_mels,
    )
    n_spk = len(ds.spk2idx)
    # split: simple random split
    from sklearn.model_selection import train_test_split
    idxs = list(range(len(ds)))
    train_idx, val_idx = train_test_split(idxs, test_size=0.1, random_state=42)
    from torch.utils.data import Subset
    train_ds = Subset(ds, train_idx)
    val_ds = Subset(ds, val_idx)

    import os as _os, platform as _platform
    if args.loader_workers >= 0:
        num_workers = args.loader_workers
    else:
        if _platform.system() == "Windows":
             num_workers = 0 # force single process on windows by default
        else:
             num_workers = max(1, (_os.cpu_count() or 2) // 2)
    
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=pad_collate, num_workers=num_workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=pad_collate, num_workers=num_workers)

    # Model
    # Need to determine feat_dim
    # We can peek at one sample
    sample_feat, _ = ds[0]
    feat_dim = int(sample_feat.shape[0])
    print(f"Feature dim: {feat_dim}, n_speakers: {n_spk}")

    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=n_spk).to(args.device)
    
    if args.optimizer == "adamw":
        optimizer = optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    else:
        optimizer = optim.Adam(model.parameters(), lr=args.lr)

    if args.loss == "aam":
        loss_fn = AAMSoftmaxLoss(s=args.aam_s, m=args.aam_m).to(args.device)
    else:
        loss_fn = nn.CrossEntropyLoss().to(args.device)

    best_acc = 0.0
    best_eer = 1.0
    no_improve = 0
    
    save_path = os.path.join(args.save_dir, args.model_name)
    
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, args.device, args.loss, loss_fn)
        val_loss, val_acc = evaluate(model, val_loader, args.device, args.loss, loss_fn)
        
        print(f"Epoch {epoch}: Train Loss={train_loss:.4f} Acc={train_acc:.4f} | Val Loss={val_loss:.4f} Acc={val_acc:.4f} | T={time.time()-t0:.1f}s")

        # EER Check
        if epoch % args.eer_interval == 0:
            print("Computing EER...")
            embs, labs = collect_embeddings(model, val_loader, args.device)
            eer = compute_eer_from_embeddings(embs, labs, max_pairs=args.eer_pairs)
            if eer is not None:
                print(f"  Val EER: {eer:.4f}")
                if eer < best_eer:
                    best_eer = eer
            else:
                print("  Val EER: skipped (not enough pairs)")

        if val_acc > best_acc:
            best_acc = val_acc
            no_improve = 0
            torch.save(model.state_dict(), save_path)
            print(f"  Saved best model to {save_path}")
        else:
            no_improve += 1
            
        if args.early_stop and no_improve >= args.patience:
            print(f"Early stopping at epoch {epoch}")
            break

    print(f"Done. Best Val Acc={best_acc:.4f}")

if __name__ == "__main__":
    main()
