import os
import torch
import numpy as np
from torch.utils.data import Dataset

class SpeakerDataset(Dataset):
    def __init__(self, feature_dir):
        self.samples = []
        self.labels = []
        self.speaker_to_label = {}

        speakers = sorted(os.listdir(feature_dir))

        for label, speaker in enumerate(speakers):
            self.speaker_to_label[speaker] = label
            speaker_dir = os.path.join(feature_dir, speaker)

            for file in os.listdir(speaker_dir):
                if file.endswith(".npy"):
                    path = os.path.join(speaker_dir, file)
                    self.samples.append(path)
                    self.labels.append(label)

        print(f"共加载 {len(self.samples)} 条语音特征")
        print(f"说话人数量: {len(self.speaker_to_label)}")

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        feature = np.load(self.samples[idx])
        feature = torch.tensor(feature, dtype=torch.float32)
        label = torch.tensor(self.labels[idx], dtype=torch.long)
        return feature, label
