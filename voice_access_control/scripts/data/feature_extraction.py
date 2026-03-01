import argparse
import os
import sys
import time
import multiprocessing as mp
import concurrent.futures as cf
import yaml
from pathlib import Path
sys.dont_write_bytecode = True

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import soundfile as sf

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import PROCESSED_DIR, FEATURES_DIR
from voice_engine.config import (
    FEATURE_TYPE_MFCC_DELTA,
    FEATURE_TYPE_LOGMEL,
    DEFAULT_N_MELS
)
# Change import to use lightweight audio_utils (No Torch dependency)
from voice_engine.core.audio_utils import extract_feature_numpy

def process_one(args):
    wav_path, out_dir, feature_type, n_mels = args
    out_path = os.path.join(out_dir, f"{Path(wav_path).stem}.npy")
    if os.path.exists(out_path):
        return os.path.basename(wav_path), None, True
    
    try:
        feat = extract_feature_numpy(wav_path, feature_type=feature_type, n_mels=n_mels)
    except Exception as e:
        print(f"Extraction failed for {wav_path}: {e}")
        return os.path.basename(wav_path), None, False

    np.save(out_path, feat)
    return os.path.basename(wav_path), feat.shape, False


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", help="Path to config yaml file")
    parser.add_argument("--in_root", default=None)
    parser.add_argument("--out_root", default=None)
    parser.add_argument("--feature_type", choices=[FEATURE_TYPE_MFCC_DELTA, FEATURE_TYPE_LOGMEL], default=None)
    parser.add_argument("--n_mels", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--feature_subdir", default=None)
    args = parser.parse_args()

    cfg = {}
    if args.config:
        if os.path.exists(args.config):
            print(f"Loading config from {args.config}")
            cfg = load_config(args.config)
        else:
            print(f"Warning: Config {args.config} not found")

    dataset_cfg = cfg.get("dataset", {})
    
    in_root_str = args.in_root or dataset_cfg.get("in_root") or str(PROCESSED_DIR)
    out_root_str = args.out_root or dataset_cfg.get("out_root") or str(FEATURES_DIR)
    feature_type = args.feature_type or dataset_cfg.get("feature_type") or FEATURE_TYPE_MFCC_DELTA
    n_mels = args.n_mels or dataset_cfg.get("n_mels") or DEFAULT_N_MELS
    workers = args.workers if args.workers is not None else dataset_cfg.get("workers", 0)
    feature_subdir = args.feature_subdir or dataset_cfg.get("feature_subdir", "")

    in_root = Path(in_root_str)
    final_subdir = feature_subdir or feature_type
    out_root = Path(out_root_str) / final_subdir
    
    if not in_root.exists():
        raise FileNotFoundError(f"Input directory not found: {in_root}")

    print(f"Extracting features from {in_root} to {out_root}")
    print(f"Feature Type: {feature_type}, N_Mels: {n_mels}")

    # Walk through all wav files
    tasks = []
    
    # Use rglob to find all wavs recursively
    wav_files = list(in_root.rglob("*.wav"))
    print(f"Found {len(wav_files)} wav files total.")

    for wav_path in wav_files:
        try:
            rel_path = wav_path.relative_to(in_root)
        except ValueError:
            rel_path = wav_path.name
            
        target_out_dir = out_root / rel_path.parent
        os.makedirs(target_out_dir, exist_ok=True)
        
        tasks.append((str(wav_path), str(target_out_dir), feature_type, n_mels))

    if not tasks:
        print("No tasks to process.")
        return

    start_all = time.perf_counter()
    
    # Fix for MemoryError on Windows: Default to fewer workers if low RAM or issues persist
    # max(1, mp.cpu_count() - 1) is too aggressive if Torch is loaded or memory is low.
    # Since we removed Torch dependency, we can be slightly more aggressive, but still safe.
    # Let's cap at 4 workers by default on Windows to be safe.
    default_workers = max(1, mp.cpu_count() - 1)
    if os.name == 'nt':
        default_workers = min(4, default_workers)
        
    final_workers = workers if workers > 0 else default_workers
    print(f"Using {final_workers} workers for {len(tasks)} tasks...")

    if final_workers == 1:
        for i, t in enumerate(tasks, 1):
            name, shape, skipped = process_one(t)
            if i % 100 == 0:
                print(f"Processed {i}/{len(tasks)}")
    else:
        ctx = mp.get_context("spawn")
        try:
            with cf.ProcessPoolExecutor(max_workers=final_workers, mp_context=ctx) as ex:
                futures = [ex.submit(process_one, t) for t in tasks]
                for i, fut in enumerate(cf.as_completed(futures), 1):
                    name, shape, skipped = fut.result()
                    if i % 100 == 0:
                         print(f"Processed {i}/{len(tasks)}")
        except KeyboardInterrupt:
            print("Interrupted by user.")
            raise

    cost_all = time.perf_counter() - start_all
    print(f"✅ Extraction complete. Time: {cost_all:.2f}s")

if __name__ == "__main__":
    mp.freeze_support()
    main()
