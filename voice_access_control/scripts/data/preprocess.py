import argparse
import os
import sys
import shutil
import random
import yaml
from pathlib import Path
import librosa
import numpy as np
import soundfile as sf
import tqdm

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import constants from config
from voice_engine.config import (
    SAMPLE_RATE,
    PRE_EMPHASIS_COEFF,
    DATA_DIR,
    RAW_DIR,      # Should be defined in config or derived
    PROCESSED_DIR # Should be defined in config or derived
)

# Fallback for paths if not in config (though they should be)
if 'RAW_DIR' not in locals():
    RAW_DIR = os.path.join(DATA_DIR, "raw")
if 'PROCESSED_DIR' not in locals():
    PROCESSED_DIR = os.path.join(DATA_DIR, "processed")

# Default paths
DEFAULT_IN_ROOT = os.path.join(DATA_DIR, "mini_vox") # Fallback to mini_vox if raw not ready
DEFAULT_OUT_ROOT = PROCESSED_DIR

def pre_emphasis(y, coeff=PRE_EMPHASIS_COEFF):
    """Apply pre-emphasis filter."""
    return np.append(y[0], y[1:] - coeff * y[:-1])

def normalize(y):
    """Normalize audio amplitude."""
    max_val = np.max(np.abs(y))
    if max_val < 1e-6:
        return y
    return y / max_val

def process_file(in_path, out_path):
    """Read, process, and write audio file."""
    try:
        # Load audio
        y, sr = sf.read(in_path)

        # Convert to mono
        if len(y.shape) > 1:
            y = y.mean(axis=1)

        # Resample
        if sr != SAMPLE_RATE:
            y = librosa.resample(y, orig_sr=sr, target_sr=SAMPLE_RATE)

        # Pre-process
        y = pre_emphasis(y)
        y = normalize(y)

        # Save
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        sf.write(out_path, y, SAMPLE_RATE)
        return True
    except Exception as e:
        print(f"Error processing {in_path}: {e}")
        return False

def get_speaker_id(filename):
    """Extract speaker ID from filename (e.g., id10012-...)."""
    parts = filename.split("-")
    if len(parts) >= 1 and parts[0].startswith("id"):
        return parts[0]
    return "unknown"

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Preprocess audio data (Resample, VAD, Normalize)")
    parser.add_argument("--config", "-c", default="configs/preprocess.yaml", help="Path to config yaml file")
    parser.add_argument("--in_root", default=None, help="Input directory (e.g., data/mini_vox)")
    parser.add_argument("--out_root", default=None, help="Output directory (e.g., data/processed)")
    parser.add_argument("--split_valid", action="store_true", default=None, help="Split valid set into valid/test")
    args = parser.parse_args()

    # Load config if available
    cfg = {}
    if args.config and os.path.exists(args.config):
        print(f"Loading config from {args.config}")
        cfg = load_config(args.config)
    
    # Priority: CLI > Config > Default
    dataset_cfg = cfg.get("dataset", {})
    in_root_str = args.in_root or dataset_cfg.get("in_root") or DEFAULT_IN_ROOT
    out_root_str = args.out_root or dataset_cfg.get("out_root") or DEFAULT_OUT_ROOT
    
    # split_valid: CLI flag overrides Config
    if args.split_valid is not None:
        split_valid = args.split_valid
    else:
        split_valid = dataset_cfg.get("split_valid", True)

    in_root = Path(in_root_str)
    out_root = Path(out_root_str)

    if not in_root.exists():
        print(f"Error: Input directory {in_root} does not exist.")
        return

    print(f"Preprocessing from {in_root} to {out_root}")
    print(f"Parameters: SR={SAMPLE_RATE}, PreEmphasis={PRE_EMPHASIS_COEFF}")
    
    # 1. Collect files
    train_files = list((in_root / "train").rglob("*.wav")) if (in_root / "train").exists() else []
    valid_files = list((in_root / "valid").rglob("*.wav")) if (in_root / "valid").exists() else []
    test_files = list((in_root / "test").rglob("*.wav")) if (in_root / "test").exists() else []
    
    # If no train/valid folders found, try searching recursively in root
    if not train_files and not valid_files and not test_files:
        print("No train/valid/test folders found. Searching recursively...")
        all_files = list(in_root.rglob("*.wav"))
        # Assume everything is train if structure is unknown
        train_files = all_files
        valid_files = []
        test_files = []

    print(f"Found {len(train_files)} train, {len(valid_files)} valid, {len(test_files)} test files.")

    # 2. Prepare Valid/Test Split (Only if test_files is empty AND split_valid is True)
    valid_speakers = set()
    test_speakers = set()
    
    if split_valid and valid_files and not test_files:
        # Group valid files by speaker
        spk_map = {}
        for f in valid_files:
            spk = get_speaker_id(f.name)
            if spk not in spk_map:
                spk_map[spk] = []
            spk_map[spk].append(f)
        
        all_spks = sorted(list(spk_map.keys()))
        random.seed(42)
        random.shuffle(all_spks)
        
        mid = len(all_spks) // 2
        valid_speakers = set(all_spks[:mid])
        test_speakers = set(all_spks[mid:])
        
        print(f"Splitting valid set: {len(valid_speakers)} speakers to Valid, {len(test_speakers)} speakers to Test.")

    # 3. Process Train
    if train_files:
        print("Processing Train...")
        for f in tqdm.tqdm(train_files):
            spk = get_speaker_id(f.name)
            # Structure: data/processed/train/{speaker_id}/{filename}
            out_path = out_root / "train" / spk / f.name
            process_file(f, out_path)

    # 4. Process Valid (and split if needed)
    if valid_files:
        print("Processing Valid...")
        for f in tqdm.tqdm(valid_files):
            spk = get_speaker_id(f.name)
            if split_valid and not test_files:
                # Use calculated split
                if spk in test_speakers:
                    split = "test"
                else:
                    split = "valid"
            else:
                # Preserve existing split
                split = "valid"
            
            out_path = out_root / split / spk / f.name
            process_file(f, out_path)

    # 5. Process Test (if exists in source)
    if test_files:
        print("Processing Test...")
        for f in tqdm.tqdm(test_files):
            spk = get_speaker_id(f.name)
            out_path = out_root / "test" / spk / f.name
            process_file(f, out_path)

    print("Preprocessing complete.")

if __name__ == "__main__":
    main()
