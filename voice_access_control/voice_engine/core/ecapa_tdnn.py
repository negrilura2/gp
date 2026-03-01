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

class AttentiveStatisticsPooling(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.tdnn = nn.Conv1d(channels, channels, 1)
        self.tanh = nn.Tanh()
        self.conv = nn.Conv1d(channels, channels, 1)

    def forward(self, x, lengths=None):
        # x: (B, C, T)
        # alpha: (B, C, T)
        alpha = self.conv(self.tanh(self.tdnn(x)))
        if lengths is not None:
            mask = torch.arange(x.size(2), device=x.device).unsqueeze(0) < lengths.unsqueeze(1)
            mask = mask.unsqueeze(1).float()  # (B, 1, T)
            alpha = alpha.masked_fill(mask == 0, -float('inf'))
        
        alpha = F.softmax(alpha, dim=2)
        mean = torch.sum(alpha * x, dim=2)
        residuals = torch.sum(alpha * x**2, dim=2) - mean**2
        std = torch.sqrt(residuals.clamp(min=1e-9))
        return torch.cat([mean, std], dim=1)

class TDNNBlock(nn.Module):
    def __init__(self, in_ch, out_ch, kern=3, dilation=1, dropout=0.1):
        super().__init__()
        self.conv = nn.Conv1d(in_ch, out_ch, kern, padding=dilation*(kern-1)//2, dilation=dilation)
        self.bn = nn.BatchNorm1d(out_ch)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=dropout) if dropout > 0 else nn.Identity()
    def forward(self, x):
        return self.dropout(self.relu(self.bn(self.conv(x))))

class LightECAPA(nn.Module):
    def __init__(self, feat_dim=39, channels=512, emb_dim=192, n_speakers=None, dropout=0.1):
        super().__init__()
        # Input Normalization: Crucial for Log-Mel features
        self.inst_norm = nn.InstanceNorm1d(feat_dim)
        
        self.layer1 = TDNNBlock(feat_dim, channels, kern=5, dropout=dropout)
        self.layer2 = TDNNBlock(channels, channels, kern=3, dropout=dropout)
        self.se = SEBlock(channels)
        
        # Aggregation: Attentive Statistics Pooling
        self.pool = AttentiveStatisticsPooling(channels)
        self.bn_pool = nn.BatchNorm1d(channels * 2)
        
        self.fc1 = nn.Linear(channels * 2, emb_dim)
        self.bn_emb = nn.BatchNorm1d(emb_dim)
        
        # classification head (for training with CE)
        if n_speakers is not None:
            self.classifier = nn.Linear(emb_dim, n_speakers)
        else:
            self.classifier = None

    def forward(self, x, lengths=None, return_embedding=False):
        # x: (B, C, T)
        x = self.inst_norm(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.se(x)
        
        # Attentive Statistics Pooling
        x = self.pool(x, lengths=lengths)  # (B, 2*C)
        x = self.bn_pool(x)
        
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
