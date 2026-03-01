# voice_engine/losses.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import math

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
