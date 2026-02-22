# voice_engine/trainer.py
import time
import os
import math
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torch.utils.tensorboard import SummaryWriter
from sklearn.model_selection import train_test_split
from .dataset import SpeakerDataset, pad_collate
from .ecapa_tdnn import LightECAPA
from .losses import AAMSoftmaxLoss
from .metrics import (
    compute_pairs_scores,
    compute_cohort_stats,
    apply_score_norm,
    compute_eer_from_embeddings,
    eer_from_roc,
    compute_mindcf,
    recommend_threshold,
    compute_score_hist,
    compute_calibration,
    extract_all_embeddings,
    build_templates,
    collect_embeddings,
)

# ==========================================
# Training Loop
# ==========================================

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

class Trainer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = cfg.get("training", {}).get("device", "cuda" if torch.cuda.is_available() else "cpu")
        self.feature_dir = cfg.get("dataset", {}).get("feature_dir", "data/features")
        self.feature_type = cfg.get("dataset", {}).get("feature_type", "mfcc_delta")
        self.n_mels = cfg.get("dataset", {}).get("n_mels", 40)
        self.dataset_mode = cfg.get("dataset", {}).get("mode", "feature")
        self.noise_dir = cfg.get("dataset", {}).get("noise_dir")
        self.save_dir = cfg.get("paths", {}).get("save_dir", "models")
        self.log_dir = cfg.get("paths", {}).get("log_dir", "reports")
        self.tensorboard_dir = cfg.get("paths", {}).get("runs_dir", "runs")
        self.strategy_dir = cfg.get("paths", {}).get("strategy_dir", os.path.join("reports", "strategy"))
        self.batch_size = cfg.get("training", {}).get("batch_size", 32)
        self.lr = cfg.get("training", {}).get("lr", 1e-3)
        self.epochs = cfg.get("training", {}).get("epochs", 40)
        self.loss_type = cfg.get("training", {}).get("loss", "ce")
        self.optimizer_type = cfg.get("training", {}).get("optimizer", "adam")
        self.loader_workers = cfg.get("dataset", {}).get("loader_workers", -1)
        self.early_stop = cfg.get("training", {}).get("early_stop", False)
        self.patience = cfg.get("training", {}).get("patience", 3)
        self.eer_interval = cfg.get("evaluation", {}).get("eer_interval", 5)
        self.eer_pairs = cfg.get("evaluation", {}).get("eer_pairs", 20000)
        
        self.model = None
        self.optimizer = None
        self.loss_fn = None
        self.train_loader = None
        self.val_loader = None
        
        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.strategy_dir, exist_ok=True)
        self.writer = SummaryWriter(log_dir=self.tensorboard_dir)

    def setup(self):
        # Dataset
        augmentor = None
        if self.noise_dir and self.dataset_mode == 'raw':
            print(f"Enabling Noise Augmentation from {self.noise_dir}")
            from .dataset import NoiseAugmentor
            augmentor = NoiseAugmentor(self.noise_dir)

        # Auto-resolve feature directory based on feature_type
        # If data/features/logmel exists, use it instead of data/features
        dataset_root = self.feature_dir
        if self.dataset_mode == 'feature':
            potential_subdir = os.path.join(self.feature_dir, self.feature_type)
            if os.path.isdir(potential_subdir):
                print(f"Auto-detected feature subdirectory: {potential_subdir}")
                dataset_root = potential_subdir

        print(f"Loading dataset from {dataset_root} (mode={self.dataset_mode})...")
        ds = SpeakerDataset(
            dataset_root,
            mode=self.dataset_mode,
            augmentor=augmentor,
            feature_type=self.feature_type,
            n_mels=self.n_mels,
        )
        n_spk = len(ds.spk2idx)
        print(f"Found {len(ds)} utterances, {n_spk} speakers.")
        
        idxs = list(range(len(ds)))
        train_idx, val_idx = train_test_split(idxs, test_size=0.1, random_state=42)
        train_ds = Subset(ds, train_idx)
        val_ds = Subset(ds, val_idx)

        import os as _os, platform as _platform
        if self.loader_workers >= 0:
            num_workers = self.loader_workers
        else:
            if _platform.system() == "Windows":
                 num_workers = 0
            else:
                 num_workers = max(1, (_os.cpu_count() or 2) // 2)

        self.train_loader = DataLoader(train_ds, batch_size=self.batch_size, shuffle=True, collate_fn=pad_collate, num_workers=num_workers)
        self.val_loader = DataLoader(val_ds, batch_size=self.batch_size, shuffle=False, collate_fn=pad_collate, num_workers=num_workers)

        # Model
        sample_feat, _ = ds[0]
        feat_dim = int(sample_feat.shape[0])
        print(f"Feature dim: {feat_dim}")
        
        self.model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=n_spk).to(self.device)

        # Optimizer
        if self.optimizer_type == "adamw":
            self.optimizer = optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=1e-4)
        else:
            self.optimizer = optim.Adam(self.model.parameters(), lr=self.lr)

        # Loss
        if self.loss_type == "aam":
            self.loss_fn = AAMSoftmaxLoss().to(self.device)
        else:
            self.loss_fn = nn.CrossEntropyLoss().to(self.device)

    def run(self):
        self.setup()
        best_acc = 0.0
        patience_counter = 0
        history = []
        total_time = 0.0
        for epoch in range(self.epochs):
            start = time.time()
            loss_train, acc_train = train_epoch(self.model, self.train_loader, self.optimizer, self.device, self.loss_type, self.loss_fn)
            loss_val, acc_val = evaluate(self.model, self.val_loader, self.device, self.loss_type, self.loss_fn)
            dur = time.time() - start
            total_time += dur
            
            print(f"Epoch {epoch+1}/{self.epochs} | T={dur:.1f}s | "
                  f"Train Loss={loss_train:.4f} Acc={acc_train:.4f} | "
                  f"Val Loss={loss_val:.4f} Acc={acc_val:.4f}")
            
            # TensorBoard logging
            self.writer.add_scalar("Loss/train", loss_train, epoch + 1)
            self.writer.add_scalar("Accuracy/train", acc_train, epoch + 1)
            self.writer.add_scalar("Loss/val", loss_val, epoch + 1)
            self.writer.add_scalar("Accuracy/val", acc_val, epoch + 1)
            
            eer_value = None
            if (epoch + 1) % self.eer_interval == 0:
                print("Computing EER...")
                embs, labels = collect_embeddings(self.model, self.val_loader, self.device)
                eer = compute_eer_from_embeddings(embs, labels, max_pairs=self.eer_pairs)
                if eer is not None:
                    print(f"  => EER: {eer:.4f}")
                    self.writer.add_scalar("EER/val", eer, epoch + 1)
                    eer_value = float(eer)

            if acc_val > best_acc:
                best_acc = acc_val
                patience_counter = 0
                torch.save(self.model.state_dict(), os.path.join(self.save_dir, "ecapa_best.pth"))
                print("  => Saved best model.")
            else:
                patience_counter += 1
                if self.early_stop and patience_counter >= self.patience:
                    print("Early stopping.")
                    break
            history.append(
                {
                    "epoch": epoch + 1,
                    "loss_train": float(loss_train),
                    "acc_train": float(acc_train),
                    "loss_val": float(loss_val),
                    "acc_val": float(acc_val),
                    "eer": eer_value,
                    "time_sec": float(dur),
                }
            )
        torch.save(self.model.state_dict(), os.path.join(self.save_dir, "ecapa_last.pth"))
        run_name = f"earlystop_pat{self.patience}" if self.early_stop else f"fixed_{self.epochs}ep"
        summary = {
            "run_name": run_name,
            "early_stop": bool(self.early_stop),
            "patience": int(self.patience),
            "epochs_planned": int(self.epochs),
            "epochs_run": len(history),
            "total_time_sec": float(total_time),
            "history": history,
        }
        out_path = os.path.join(self.strategy_dir, f"{run_name}.json")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def fit(self):
        self.run()
