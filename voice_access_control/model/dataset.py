import os
import numpy as np
import torch
from torch.utils.data import Dataset

class VoiceDataset(Dataset):
    def __init__(self, feature_root):
        self.samples = []
        self.labels = {}
        label_id = 0

        for user in os.listdir(feature_root):
            if user not in self.labels:
                self.labels[user] = label_id
                label_id += 1

            user_dir = os.path.join(feature_root, user)
            for file in os.listdir(user_dir):
                if file.endswith(".npy"):
                    self.samples.append(
                        (os.path.join(user_dir, file), self.labels[user])
                    )

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        mfcc = np.load(path)
        return torch.tensor(mfcc, dtype=torch.float32), label
