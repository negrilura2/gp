import argparse
import os
import sys
import numpy as np
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import FEATURES_DIR

def find_first_feature(root):
    for base, _, files in os.walk(root):
        for name in files:
            if name.endswith(".npy"):
                return os.path.join(base, name)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--feat", type=str, default=None)
    args = parser.parse_args()

    feat_path = args.feat or find_first_feature(FEATURES_DIR)
    if not feat_path:
        raise FileNotFoundError("features 目录下未找到 .npy")

    feat = np.load(feat_path)
    plt.figure(figsize=(8, 4))
    plt.imshow(feat.T, aspect="auto", origin="lower")
    plt.colorbar()
    plt.title("MFCC Feature Map")
    plt.xlabel("Frame Index")
    plt.ylabel("MFCC Coefficients")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
