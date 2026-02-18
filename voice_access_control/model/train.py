# model/train.py
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
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--optimizer", choices=["adam", "adamw"], default="adam")
    parser.add_argument("--loss", choices=["ce", "aam"], default="ce")
    parser.add_argument("--aam_s", type=float, default=30.0)
    parser.add_argument("--aam_m", type=float, default=0.2)
    parser.add_argument("--eer_pairs", type=int, default=20000)
    parser.add_argument("--feature_tag", default="default")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    ds = SpeakerDataset(args.feature_dir)
    n_spk = len(ds.spk2idx)
    # split: simple random split
    from sklearn.model_selection import train_test_split
    idxs = list(range(len(ds)))
    train_idx, val_idx = train_test_split(idxs, test_size=0.1, random_state=42)
    from torch.utils.data import Subset
    train_ds = Subset(ds, train_idx)
    val_ds = Subset(ds, val_idx)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, collate_fn=pad_collate, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, collate_fn=pad_collate, num_workers=2)

    if len(ds) == 0:
        raise ValueError("feature_dir 内没有可用特征文件")
    sample_feat, _ = ds[0]
    feat_dim = int(sample_feat.shape[0])
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=n_spk).to(args.device)
    if args.optimizer == "adamw":
        opt = optim.AdamW(model.parameters(), lr=args.lr)
    else:
        opt = optim.Adam(model.parameters(), lr=args.lr)
    if args.loss == "aam":
        loss_fn = AAMSoftmaxLoss(s=args.aam_s, m=args.aam_m)
    else:
        loss_fn = nn.CrossEntropyLoss()
    best_val = 1e9
    history = []
    for epoch in range(1, args.epochs+1):
        t0 = time.time()
        train_loss, train_acc = train_epoch(model, train_loader, opt, args.device, args.loss, loss_fn)
        val_loss, val_acc = evaluate(model, val_loader, args.device, args.loss, loss_fn)
        embs, lbs = collect_embeddings(model, val_loader, args.device)
        val_eer = compute_eer_from_embeddings(embs, lbs, max_pairs=args.eer_pairs)
        dt = time.time() - t0
        print(
            f"Epoch {epoch}  train_loss={train_loss:.4f}  train_acc={train_acc:.4f}  "
            f"val_loss={val_loss:.4f}  val_acc={val_acc:.4f}  val_eer={val_eer if val_eer is not None else 'NA'}  time={dt:.1f}s"
        )
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "train_acc": train_acc,
                "val_loss": val_loss,
                "val_acc": val_acc,
                "val_eer": val_eer,
                "time_sec": dt,
            }
        )
        # save
        torch.save(model.state_dict(), os.path.join(args.save_dir, f"ecapa_epoch{epoch}.pth"))
        if val_loss < best_val:
            best_val = val_loss
            torch.save(model.state_dict(), os.path.join(args.save_dir, "ecapa_best.pth"))
        tag = args.feature_tag or "default"
        csv_path = os.path.join(args.log_dir, f"train_metrics_{tag}.csv")
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["epoch", "train_loss", "train_acc", "val_loss", "val_acc", "val_eer", "time_sec"],
            )
            writer.writeheader()
            writer.writerows(history)
        json_path = os.path.join(args.log_dir, f"train_metrics_{tag}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        epochs = [h["epoch"] for h in history]
        plt.figure(figsize=(7, 4))
        plt.plot(epochs, [h["train_loss"] for h in history], label="train_loss")
        plt.plot(epochs, [h["val_loss"] for h in history], label="val_loss")
        plt.xlabel("Epoch")
        plt.ylabel("Loss")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(args.log_dir, f"loss_curve_{tag}.png"))
        plt.close()
        plt.figure(figsize=(7, 4))
        plt.plot(epochs, [h["train_acc"] for h in history], label="train_acc")
        plt.plot(epochs, [h["val_acc"] for h in history], label="val_acc")
        plt.xlabel("Epoch")
        plt.ylabel("Accuracy")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(args.log_dir, f"acc_curve_{tag}.png"))
        plt.close()
        eer_vals = [h["val_eer"] for h in history if h["val_eer"] is not None]
        if len(eer_vals) == len(history):
            plt.figure(figsize=(7, 4))
            plt.plot(epochs, [h["val_eer"] for h in history], label="val_eer")
            plt.xlabel("Epoch")
            plt.ylabel("EER")
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(args.log_dir, f"eer_curve_{tag}.png"))
            plt.close()
        loss_vals = np.array([h["val_loss"] for h in history], dtype=float)
        acc_vals = np.array([h["val_acc"] for h in history], dtype=float)
        loss_min, loss_max = float(loss_vals.min()), float(loss_vals.max())
        acc_min, acc_max = float(acc_vals.min()), float(acc_vals.max())
        if loss_max > loss_min:
            loss_norm = (loss_vals - loss_min) / (loss_max - loss_min)
        else:
            loss_norm = loss_vals
        if acc_max > acc_min:
            acc_norm = (acc_vals - acc_min) / (acc_max - acc_min)
        else:
            acc_norm = acc_vals
        plt.figure(figsize=(7, 4))
        plt.plot(epochs, loss_norm, label="val_loss_norm")
        plt.plot(epochs, acc_norm, label="val_acc_norm")
        plt.xlabel("Epoch")
        plt.ylabel("Normalized Trend")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(args.log_dir, f"trend_curve_{tag}.png"))
        plt.close()
    print("Training finished")

if __name__ == "__main__":
    main()
