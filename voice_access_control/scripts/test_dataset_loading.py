import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from voice_engine.core.dataset import SpeakerDataset

print("Testing SpeakerDataset with Flat Structure...")
try:
    ds = SpeakerDataset("data/raw/mini_vox/train", mode="raw")
    print(f"Success! Loaded {len(ds)} samples.")
    if len(ds) > 0:
        print(f"Sample 0: {ds.samples[0]}")
except Exception as e:
    print(f"Failed: {e}")
