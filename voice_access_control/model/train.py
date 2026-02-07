from dataset import SpeakerDataset

dataset = SpeakerDataset("../data/features")

x, y = dataset[0]
print("特征形状:", x.shape)   # 应该是 (时间帧, 39)
print("标签:", y)
