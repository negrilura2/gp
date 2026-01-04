import numpy as np
import matplotlib.pyplot as plt

feat = np.load("data/features/user01/001.npy")

plt.figure(figsize=(8, 4))
plt.imshow(feat.T, aspect="auto", origin="lower")
plt.colorbar()
plt.title("MFCC Feature Map")
plt.xlabel("Frame Index")
plt.ylabel("MFCC Coefficients")
plt.tight_layout()
plt.show()
