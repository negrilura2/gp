# voice_engine/trainer.py
import time
import os
import math
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torch.utils.tensorboard import SummaryWriter
from sklearn.model_selection import train_test_split
from ..config import (
    EMBEDDING_DIM
)
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
        
        # Add slight noise to training data to prevent exact memorization
        if model.training:
             noise = torch.randn_like(feats) * 0.005 
             feats = feats + noise
             
        opt.zero_grad()
        if loss_type == "aam":
            emb = model(feats, lengths, return_embedding=True)
            loss, logits = loss_fn(emb, labels, model.classifier.weight)
        else:
            logits, _ = model(feats, lengths)
            loss = loss_fn(logits, labels)
        loss.backward()
        
        # Gradient Clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=3.0)
        
        opt.step()
        total_loss += loss.item()
        preds = torch.argmax(logits, dim=1)
        total_correct += (preds == labels).sum().item()
        total_count += labels.numel()
    
    steps = batch_idx + 1
    avg_loss = total_loss / steps if steps > 0 else 0.0
    acc = total_correct / total_count if total_count else 0.0
    return avg_loss, acc

def evaluate(model, loader, device, loss_type, loss_fn):
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_count = 0
    
    # Check output dim to avoid crash on Open Set labels
    out_dim = model.classifier.out_features if hasattr(model, 'classifier') else 0
    
    with torch.no_grad():
        for batch_idx, (feats, lengths, labels) in enumerate(loader):
            feats = feats.to(device)
            lengths = lengths.to(device)
            labels = labels.to(device)
            
            # Check for invalid labels (Open Set protection)
            if labels.max() >= out_dim:
                # Skip batch or just don't compute loss
                continue

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
            
    steps = batch_idx + 1 if 'batch_idx' in locals() else 0
    if steps == 0 or total_count == 0:
        return 0.0, 0.0

    avg_loss = total_loss / steps
    acc = total_correct / total_count
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
        self.tensorboard_root = cfg.get("paths", {}).get("runs_dir", "runs")
        self.strategy_dir = cfg.get("paths", {}).get("strategy_dir", os.path.join("reports", "strategy"))
        self.batch_size = cfg.get("training", {}).get("batch_size", 32)
        self.lr = cfg.get("training", {}).get("lr", 1e-3)
        self.epochs = cfg.get("training", {}).get("epochs", 40)
        self.loss_type = cfg.get("training", {}).get("loss", "ce")
        self.optimizer_type = cfg.get("training", {}).get("optimizer", "adam")
        self.aam_s = cfg.get("training", {}).get("aam_s", 30.0)
        self.aam_m = cfg.get("training", {}).get("aam_m", 0.2)
        self.loader_workers = cfg.get("dataset", {}).get("loader_workers", -1)
        self.early_stop = cfg.get("training", {}).get("early_stop", False)
        self.patience = cfg.get("training", {}).get("patience", 3)
        self.eer_interval = cfg.get("evaluation", {}).get("eer_interval", 5)
        self.eer_pairs = cfg.get("evaluation", {}).get("eer_pairs", 20000)
        
        self.dropout = cfg.get("model", {}).get("dropout", 0.1)
        self.channels = cfg.get("model", {}).get("n_channels", 512)
        self.weight_decay = cfg.get("training", {}).get("weight_decay", 1e-3) 
        self.pretrained_path = cfg.get("model", {}).get("pretrained_path", None)

        exp_cfg = cfg.get("experiment", {}) if isinstance(cfg.get("experiment", {}), dict) else {}
        exp_name = exp_cfg.get("name")
        if not exp_name:
            exp_name = f"ecapa_{self.feature_type}"
        timestamp = time.strftime("%b%d_%H-%M")
        self.tensorboard_dir = os.path.join(self.tensorboard_root, f"{timestamp}_{exp_name}")

        self.model = None
        self.optimizer = None
        self.loss_fn = None
        self.train_loader = None
        self.val_loader = None
        
        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.strategy_dir, exist_ok=True)
        os.makedirs(self.tensorboard_dir, exist_ok=True)
        self.writer = SummaryWriter(log_dir=self.tensorboard_dir)

    def setup(self):
        # Dataset
        augmentor = None
        if self.noise_dir and self.dataset_mode == 'raw':
            print(f"Enabling Noise Augmentation from {self.noise_dir}")
            from .dataset import NoiseAugmentor
            augmentor = NoiseAugmentor(self.noise_dir)

        train_dir = self.cfg.get("dataset", {}).get("train_dir")
        val_dir = self.cfg.get("dataset", {}).get("val_dir")
        
        dataset_root = self.feature_dir
        if self.dataset_mode == 'feature':
            potential_subdir = os.path.join(self.feature_dir, self.feature_type)
            if os.path.isdir(potential_subdir):
                if not (train_dir and os.path.exists(train_dir)):
                    print(f"Auto-detected feature subdirectory: {potential_subdir}")
                    dataset_root = potential_subdir
        
        train_ds = None
        val_ds = None
        
        if train_dir and val_dir and os.path.exists(train_dir) and os.path.exists(val_dir):
            print(f"Using explicit Train/Val split from config:")
            print(f"  Train: {train_dir}")
            print(f"  Val:   {val_dir}")
            
            train_ds = SpeakerDataset(
                train_dir,
                mode=self.dataset_mode,
                augmentor=augmentor,
                feature_type=self.feature_type,
                n_mels=self.n_mels,
                spec_augment=True,
            )
            
            # Try Closed-Set Validation first (assume Valid speakers are in Train)
            # This allows computing Classification Loss/Accuracy correctly.
            print("Attempting Closed-Set Validation (applying Train label mapping to Val)...")
            
            # Determine validation mode: if Val Dir points to Features, force 'feature' mode
            # unless config explicitly says otherwise (but usually val_dir in config implies a specific type)
            val_mode = self.dataset_mode
            if "features" in val_dir and self.dataset_mode == "raw":
                 print(f"Notice: Training in 'raw' mode but Validation dir seems to be features ('{val_dir}'). Switching Validation mode to 'feature'.")
                 val_mode = "feature"

            val_ds = SpeakerDataset(
                val_dir,
                mode=val_mode,
                augmentor=None,
                feature_type=self.feature_type,
                n_mels=self.n_mels,
                class_mapping=train_ds.spk2idx, # Share mapping
                spec_augment=False,
            )
            
            # Fallback for Open-Set (if Valid speakers are disjoint from Train)
            if len(val_ds) == 0:
                print("Warning: No validation samples found with Train mapping (Open-Set detected).")
                print("         Reloading Validation set without label mapping.")
                val_ds = SpeakerDataset(
                    val_dir,
                    mode=val_mode,
                    augmentor=None,
                    feature_type=self.feature_type,
                    n_mels=self.n_mels,
                    class_mapping=None, # Independent mapping
                    spec_augment=False,
                )
            else:
                print(f"Successfully loaded {len(val_ds)} validation samples using Train mapping.")

            ds = train_ds 
            
        else:
            print(f"Loading single dataset from {dataset_root} (mode={self.dataset_mode}) and doing random split...")
            ds = SpeakerDataset(
                dataset_root,
                mode=self.dataset_mode,
                augmentor=augmentor,
                feature_type=self.feature_type,
                n_mels=self.n_mels,
                spec_augment=False 
            )
            print(f"Found {len(ds)} utterances, {len(ds.spk2idx)} speakers.")
            
            idxs = list(range(len(ds)))
            train_idx, val_idx = train_test_split(idxs, test_size=0.1, random_state=42)
            
            print("Re-initializing datasets for Train/Val split to ensure correct augmentation...")
            train_ds_full = SpeakerDataset(
                dataset_root,
                mode=self.dataset_mode,
                augmentor=augmentor,
                feature_type=self.feature_type,
                n_mels=self.n_mels,
                spec_augment=True 
            )
            val_ds_full = SpeakerDataset(
                dataset_root,
                mode=self.dataset_mode,
                augmentor=None,
                feature_type=self.feature_type,
                n_mels=self.n_mels,
                spec_augment=False 
            )
            train_ds = Subset(train_ds_full, train_idx)
            val_ds = Subset(val_ds_full, val_idx)
            # In random split mode, speakers are shared, so class_mapping is consistent implicitly

        n_spk = len(train_ds.spk2idx) if hasattr(train_ds, "spk2idx") else len(ds.spk2idx)
        print(f"Training on {len(train_ds)} samples, {n_spk} speakers.")
        print(f"Validating on {len(val_ds)} samples.")

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

        # Check for label consistency between Train and Val
        self.val_label_mismatch = False
        if hasattr(train_ds, "dataset") and isinstance(train_ds, Subset):
             # Random split from same parent -> Consistent
             pass
        elif hasattr(train_ds, "spk2idx") and hasattr(val_ds, "spk2idx"):
             # Explicit split -> Check if mappings are identical
             if train_ds.spk2idx != val_ds.spk2idx:
                 print("Notice: Validation set has different speaker-to-label mapping than Training set.")
                 print("        Classification Loss/Accuracy on Validation set will be meaningless (Open Set).")
                 print("        Will rely on EER for validation metrics.")
                 self.val_label_mismatch = True

        sample_feat, _ = ds[0]
        # sample_feat is (T, D) for features, so dim is shape[1]. If raw audio (T,), dim is 1.
        feat_dim = int(sample_feat.shape[1]) if sample_feat.ndim > 1 else 1
        print(f"Feature dim: {feat_dim}, Channels: {self.channels}, Dropout: {self.dropout}")
        
        self.model = LightECAPA(feat_dim=feat_dim, channels=self.channels, emb_dim=192, n_speakers=n_spk, dropout=self.dropout).to(self.device)

        # Load Pretrained Weights if available
        if self.pretrained_path and os.path.exists(self.pretrained_path):
            print(f"Loading pretrained weights from {self.pretrained_path}...")
            try:
                state_dict = torch.load(self.pretrained_path, map_location=self.device)
                
                # Filter out mismatching keys (e.g. classification head if n_speakers changed)
                model_dict = self.model.state_dict()
                filtered_dict = {k: v for k, v in state_dict.items() if k in model_dict and v.shape == model_dict[k].shape}
                
                if len(filtered_dict) < len(state_dict):
                    print(f"Warning: {len(state_dict) - len(filtered_dict)} layers were skipped due to shape mismatch (e.g. classifier head).")
                
                model_dict.update(filtered_dict)
                self.model.load_state_dict(model_dict)
                print("Pretrained weights loaded successfully.")
            except Exception as e:
                print(f"Error loading pretrained weights: {e}")

        if self.optimizer_type == "adamw":
            self.optimizer = optim.AdamW(self.model.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        else:
            self.optimizer = optim.Adam(self.model.parameters(), lr=self.lr, weight_decay=self.weight_decay)

        self.scheduler = CosineAnnealingLR(self.optimizer, T_max=self.epochs, eta_min=1e-6)

        if self.loss_type == "aam":
            self.loss_fn = AAMSoftmaxLoss(s=self.aam_s, m=self.aam_m).to(self.device)
        else:
            self.loss_fn = nn.CrossEntropyLoss().to(self.device)

    def run(self):
        self.setup()
        best_eer = None
        patience_counter = 0
        history = []
        total_time = 0.0
        
        for epoch in range(self.epochs):
            start = time.time()
            loss_train, acc_train = train_epoch(self.model, self.train_loader, self.optimizer, self.device, self.loss_type, self.loss_fn)
            
            # Evaluate Loss/Acc
            if self.val_label_mismatch:
                loss_val, acc_val = 0.0, 0.0
                val_msg = "Val Loss=N/A (OpenSet) Acc=N/A"
            else:
                loss_val, acc_val = evaluate(self.model, self.val_loader, self.device, self.loss_type, self.loss_fn)
                val_msg = f"Val Loss={loss_val:.4f} Acc={acc_val:.4f}"
            
            dur = time.time() - start
            total_time += dur
            
            print(f"Epoch {epoch+1}/{self.epochs} | T={dur:.1f}s | "
                  f"Train Loss={loss_train:.4f} Acc={acc_train:.4f} | {val_msg}")
            
            # TensorBoard logging
            current_lr = self.optimizer.param_groups[0]['lr']
            self.writer.add_scalar("LR", current_lr, epoch + 1)
            self.writer.add_scalar("Loss/train", loss_train, epoch + 1)
            self.writer.add_scalar("Accuracy/train", acc_train, epoch + 1)
            
            if not self.val_label_mismatch:
                self.writer.add_scalar("Loss/val", loss_val, epoch + 1)
                self.writer.add_scalar("Accuracy/val", acc_val, epoch + 1)
            
            self.scheduler.step()

            eer_value = None
            if (epoch + 1) % self.eer_interval == 0:
                print("Computing EER...")
                embs, labels = collect_embeddings(self.model, self.val_loader, self.device)
                
                # If Open Set, labels are 0..N_val.
                # EER needs at least 2 speakers.
                if len(np.unique(labels)) < 2:
                    print("  => EER: Skipped (Need at least 2 speakers)")
                else:
                    eer = compute_eer_from_embeddings(embs, labels, max_pairs=self.eer_pairs)
                    if eer is not None:
                        print(f"  => EER: {eer:.4f}")
                        self.writer.add_scalar("EER/val", eer, epoch + 1)
                        eer_value = float(eer)

            # Save logic: Prefer EER if available, else Val Loss
            save_best = False
            if eer_value is not None:
                if best_eer is None or eer_value < best_eer:
                    best_eer = eer_value
                    save_best = True
                    print(f"  => New Best EER: {best_eer:.4f}")
            # Fallback if EER is not computed this epoch or never
            elif best_eer is None and loss_val > 0:
                 # Logic for loss-based saving?
                 # Current code only saves on EER improvement.
                 pass

            if save_best:
                patience_counter = 0
                save_name = f"ecapa_{self.feature_type}_best.pth"
                save_path = os.path.join(self.save_dir, save_name)
                torch.save(self.model.state_dict(), save_path)
                
                meta_name = f"ecapa_{self.feature_type}_best.json"
                meta_path = os.path.join(self.save_dir, meta_name)
                with open(meta_path, "w") as f:
                    json.dump({
                        "feature_type": self.feature_type,
                        "n_mels": self.n_mels,
                        "feat_dim": self.model.layer1.conv.weight.shape[1],
                        "emb_dim": EMBEDDING_DIM,
                        "model_type": "LightECAPA"
                    }, f, indent=2)
            else:
                if eer_value is not None: # Only count patience if we computed EER
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
        
        last_name = f"ecapa_{self.feature_type}_last.pth"
        last_path = os.path.join(self.save_dir, last_name)
        torch.save(self.model.state_dict(), last_path)
        
        meta_name = f"ecapa_{self.feature_type}_last.json"
        meta_path = os.path.join(self.save_dir, meta_name)
        with open(meta_path, "w") as f:
            json.dump({
                "feature_type": self.feature_type,
                "n_mels": self.n_mels,
                "feat_dim": self.model.layer1.conv.weight.shape[1],
                "emb_dim": EMBEDDING_DIM,
                "model_type": "LightECAPA"
            }, f, indent=2)

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
