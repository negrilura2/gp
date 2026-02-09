# model/train.py
import argparse, os, time
import torch
from torch.utils.data import DataLoader
import torch.nn as nn
import torch.optim as optim
from .dataset import SpeakerDataset, pad_collate
from .ecapa_tdnn import LightECAPA

def train_epoch(model, loader, opt, device):
    model.train()
    total_loss = 0.0
    criterion = nn.CrossEntropyLoss()
    for batch_idx, (feats, lengths, labels) in enumerate(loader):
        feats = feats.to(device)         # (B, C, T)
        lengths = lengths.to(device)
        labels = labels.to(device)
        opt.zero_grad()
        logits, _ = model(feats, lengths)
        loss = criterion(logits, labels)
        loss.backward()
        opt.step()
        total_loss += loss.item()
    return total_loss / (batch_idx+1)

def evaluate(model, loader, device):
    model.eval()
    total_loss = 0.0
    criterion = nn.CrossEntropyLoss()
    with torch.no_grad():
        for batch_idx, (feats, lengths, labels) in enumerate(loader):
            feats = feats.to(device)
            lengths = lengths.to(device)
            labels = labels.to(device)
            logits, _ = model(feats, lengths)
            loss = criterion(logits, labels)
            total_loss += loss.item()
    return total_loss / (batch_idx+1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature_dir", default="data/features")
    parser.add_argument("--save_dir", default="models")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    args = parser.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)
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

    model = LightECAPA(feat_dim=39, emb_dim=192, n_speakers=n_spk).to(args.device)
    opt = optim.AdamW(model.parameters(), lr=args.lr)
    best_val = 1e9
    for epoch in range(1, args.epochs+1):
        t0 = time.time()
        train_loss = train_epoch(model, train_loader, opt, args.device)
        val_loss = evaluate(model, val_loader, args.device)
        dt = time.time() - t0
        print(f"Epoch {epoch}  train_loss={train_loss:.4f}  val_loss={val_loss:.4f}  time={dt:.1f}s")
        # save
        torch.save(model.state_dict(), os.path.join(args.save_dir, f"ecapa_epoch{epoch}.pth"))
        if val_loss < best_val:
            best_val = val_loss
            torch.save(model.state_dict(), os.path.join(args.save_dir, "ecapa_best.pth"))
    print("Training finished")

if __name__ == "__main__":
    main()
