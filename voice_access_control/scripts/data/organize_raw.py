import os
import shutil
import glob
import random
from pathlib import Path

# Configuration
# Try to find source in potential locations (handle Chinese folder name)
POTENTIAL_SOURCES = [
    Path("data/数据/mini_vox"),
    Path("data/mini_vox"),
]
SOURCE_ROOT = next((p for p in POTENTIAL_SOURCES if p.exists()), Path("data/mini_vox"))

DEST_ROOT = Path("data/raw")
TRAIN_SRC = SOURCE_ROOT / "train"
VALID_SRC = SOURCE_ROOT / "valid"

def get_speaker_id(filename):
    # Filename format: id10012-0AXjxNXiEzo-00001.wav
    # Speaker ID: id10012
    parts = filename.split("-")
    if len(parts) >= 1:
        return parts[0]
    return "unknown"

def organize():
    if not SOURCE_ROOT.exists():
        print(f"Error: Source directory {SOURCE_ROOT} does not exist.")
        return

    print(f"Organizing data from {SOURCE_ROOT} to {DEST_ROOT}...")

    # Create destination directories
    for split in ["train", "valid", "test"]:
        (DEST_ROOT / split).mkdir(parents=True, exist_ok=True)

    # 1. Process Train
    # Move all train speakers to data/raw/train
    if TRAIN_SRC.exists():
        print("Processing Train set...")
        wavs = list(TRAIN_SRC.glob("*.wav"))
        print(f"Found {len(wavs)} wav files in {TRAIN_SRC}")
        
        for wav_path in wavs:
            spk_id = get_speaker_id(wav_path.name)
            dest_dir = DEST_ROOT / "train" / spk_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wav_path, dest_dir / wav_path.name)
    else:
        print(f"Warning: {TRAIN_SRC} not found.")

    # 2. Process Valid (and split into Valid/Test)
    # We will split speakers 50/50 for Valid and Test
    if VALID_SRC.exists():
        print("Processing Valid set (splitting into valid/test)...")
        wavs = list(VALID_SRC.glob("*.wav"))
        print(f"Found {len(wavs)} wav files in {VALID_SRC}")

        # Group by speaker
        spk_map = {}
        for wav_path in wavs:
            spk_id = get_speaker_id(wav_path.name)
            if spk_id not in spk_map:
                spk_map[spk_id] = []
            spk_map[spk_id].append(wav_path)
        
        all_speakers = list(spk_map.keys())
        random.seed(42)
        random.shuffle(all_speakers)
        
        # Split speakers
        split_idx = len(all_speakers) // 2
        valid_spks = all_speakers[:split_idx]
        test_spks = all_speakers[split_idx:]
        
        print(f"Total Valid/Test Speakers: {len(all_speakers)}")
        print(f"Assigning {len(valid_spks)} speakers to Valid")
        print(f"Assigning {len(test_spks)} speakers to Test")

        # Copy files
        for spk in valid_spks:
            dest_dir = DEST_ROOT / "valid" / spk
            dest_dir.mkdir(parents=True, exist_ok=True)
            for wav_path in spk_map[spk]:
                shutil.copy2(wav_path, dest_dir / wav_path.name)

        for spk in test_spks:
            dest_dir = DEST_ROOT / "test" / spk
            dest_dir.mkdir(parents=True, exist_ok=True)
            for wav_path in spk_map[spk]:
                shutil.copy2(wav_path, dest_dir / wav_path.name)

    else:
        print(f"Warning: {VALID_SRC} not found.")

    print("Organization complete.")

if __name__ == "__main__":
    organize()
