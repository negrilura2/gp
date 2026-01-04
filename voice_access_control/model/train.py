import torch
from torch.utils.data import DataLoader
import torch.nn as nn
from ecapa_tdnn import ECAPA_TDNN
from dataset import VoiceDataset

EPOCHS = 20
BATCH_SIZE = 8
LR = 0.001

dataset = VoiceDataset("data/features")
loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

num_classes = len(dataset.labels)
model = ECAPA_TDNN(num_classes=num_classes)
optimizer = torch.optim.Adam(model.parameters(), lr=LR)
criterion = nn.CrossEntropyLoss()

model.train()
for epoch in range(EPOCHS):
    total_loss = 0
    for x, y in loader:
        _, logits = model(x)
        loss = criterion(logits, y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    print(f"Epoch {epoch+1}, Loss: {total_loss:.4f}")

torch.save(model.state_dict(), "ecapa_model.pth")
print("模型训练完成")
