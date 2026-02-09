# model/ecapa_tdnn.py
import torch
import torch.nn as nn
import torch.nn.functional as F

class SEBlock(nn.Module):
    def __init__(self, ch, r=8):
        super().__init__()
        self.fc1 = nn.Conv1d(ch, ch // r, 1)
        self.fc2 = nn.Conv1d(ch // r, ch, 1)
    def forward(self, x):
        # x: (B, C, T)
        s = x.mean(dim=2, keepdim=True)   # (B, C, 1)
        s = F.relu(self.fc1(s))
        s = torch.sigmoid(self.fc2(s))
        return x * s

class TDNNBlock(nn.Module):
    def __init__(self, in_ch, out_ch, kern=3, dilation=1):
        super().__init__()
        self.conv = nn.Conv1d(in_ch, out_ch, kern, padding=dilation*(kern-1)//2, dilation=dilation)
        self.bn = nn.BatchNorm1d(out_ch)
        self.relu = nn.ReLU()
    def forward(self, x):
        return self.relu(self.bn(self.conv(x)))

class LightECAPA(nn.Module):
    def __init__(self, feat_dim=39, channels=512, emb_dim=192, n_speakers=None):
        super().__init__()
        self.layer1 = TDNNBlock(feat_dim, 512, kern=5)
        self.layer2 = TDNNBlock(512, 512, kern=3)
        self.se = SEBlock(512)
        # aggregation: statistics pooling -> FC -> embedding
        self.pool = nn.AdaptiveAvgPool1d(1)  # simple avg pool
        self.fc1 = nn.Linear(512, emb_dim)
        self.bn_emb = nn.BatchNorm1d(emb_dim)
        # classification head (for training with CE)
        if n_speakers is not None:
            self.classifier = nn.Linear(emb_dim, n_speakers)
        else:
            self.classifier = None

    def forward(self, x, lengths=None, return_embedding=False):
        # x: (B, C, T)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.se(x)
        # mean pooling over time (masking by lengths optional)
        # if lengths given, use masked mean
        if lengths is not None:
            # lengths: (B,)
            mask = torch.arange(x.size(2), device=x.device).unsqueeze(0) < lengths.unsqueeze(1)
            mask = mask.unsqueeze(1).float()  # (B,1,T)
            x = (x * mask).sum(dim=2) / (mask.sum(dim=2) + 1e-9)  # (B, C)
        else:
            x = x.mean(dim=2)
        emb = self.fc1(x)            # (B, emb_dim)
        emb = self.bn_emb(emb)
        emb = F.normalize(emb, p=2, dim=1)
        if return_embedding:
            return emb
        if self.classifier is not None:
            logits = self.classifier(emb)
            return logits, emb
        else:
            return emb
