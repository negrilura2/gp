import torch
import torch.nn as nn
import torch.nn.functional as F

# Squeeze-and-Excitation
class SEBlock(nn.Module):
    def __init__(self, channels, reduction=8):
        super().__init__()
        self.fc1 = nn.Linear(channels, channels // reduction)
        self.fc2 = nn.Linear(channels // reduction, channels)

    def forward(self, x):
        # x: [B, C, T]
        s = x.mean(dim=2)
        s = F.relu(self.fc1(s))
        s = torch.sigmoid(self.fc2(s))
        return x * s.unsqueeze(2)


class TDNNBlock(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=5):
        super().__init__()
        self.conv = nn.Conv1d(
            in_channels, out_channels,
            kernel_size=kernel_size,
            padding=kernel_size // 2
        )
        self.bn = nn.BatchNorm1d(out_channels)
        self.se = SEBlock(out_channels)

    def forward(self, x):
        x = F.relu(self.bn(self.conv(x)))
        return self.se(x)


class ECAPA_TDNN(nn.Module):
    def __init__(self, input_dim=39, embedding_dim=192, num_classes=10):
        super().__init__()

        self.layer1 = TDNNBlock(input_dim, 128)
        self.layer2 = TDNNBlock(128, 128)
        self.layer3 = TDNNBlock(128, 128)

        self.pooling = nn.AdaptiveAvgPool1d(1)
        self.fc = nn.Linear(128, embedding_dim)
        self.classifier = nn.Linear(embedding_dim, num_classes)

    def forward(self, x):
        # x: [B, T, F] → [B, F, T]
        x = x.transpose(1, 2)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)

        x = self.pooling(x).squeeze(2)
        emb = self.fc(x)
        emb = F.normalize(emb, dim=1)

        logits = self.classifier(emb)
        return emb, logits
