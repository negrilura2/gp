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
# 移除冗余的 import
# from python_speech_features import mfcc, delta, logfbank

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import PROCESSED_DIR, FEATURES_DIR
from voice_engine.config import (
    FEATURE_TYPE_MFCC,
    FEATURE_TYPE_MFCC_DELTA,
    FEATURE_TYPE_LOGMEL,
    DEFAULT_N_MELS
)
from voice_engine.core.dataset import extract_feature_numpy

def process_one(args):
    wav_path, out_dir, feature_type, n_mels = args
    out_path = os.path.join(out_dir, f"{Path(wav_path).stem}.npy")
    if os.path.exists(out_path):
        return os.path.basename(wav_path), None, True
    
    # 使用统一的提取逻辑，不再重复造轮子
    try:
        feat = extract_feature_numpy(wav_path, feature_type=feature_type, n_mels=n_mels)
        # 注意: extract_feature_numpy 返回 (T, dim)
        # 如果需要保持旧版格式一致性，这里应该就是 (T, dim)
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
    parser.add_argument("--feature_type", choices=[FEATURE_TYPE_MFCC, FEATURE_TYPE_MFCC_DELTA, FEATURE_TYPE_LOGMEL], default=None)
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
    
    # Priority: CLI > Config > Default
    in_root_str = args.in_root or dataset_cfg.get("in_root") or str(PROCESSED_DIR)
    out_root_str = args.out_root or dataset_cfg.get("out_root") or str(FEATURES_DIR)
    feature_type = args.feature_type or dataset_cfg.get("feature_type") or FEATURE_TYPE_MFCC_DELTA
    n_mels = args.n_mels or dataset_cfg.get("n_mels") or DEFAULT_N_MELS
    workers = args.workers if args.workers is not None else dataset_cfg.get("workers", 0)
    feature_subdir = args.feature_subdir or dataset_cfg.get("feature_subdir", "")

    in_root = Path(in_root_str)
    # feature_subdir = feature_subdir or feature_type # Logic below handles this
    
    # Logic from original script
    final_subdir = feature_subdir or feature_type
    out_root = Path(out_root_str) / final_subdir
    if not in_root.exists():
        raise FileNotFoundError(in_root)

    for user_dir in in_root.iterdir():
        if not user_dir.is_dir():
            continue
            
        wav_list = [w for w in user_dir.iterdir() if w.suffix.lower() == ".wav"]
        if not wav_list:
            continue
            
        print(f"\n🎤 正在提取目录 {user_dir.name} ，共 {len(wav_list)} 条")
        
        # Check if filenames contain ID prefix (VoxCeleb style: id10001-video-00001.wav)
        # We group tasks by (out_dir, wav_path)
        tasks = []
        
        for w in wav_list:
            # Try to parse ID from filename
            fname = w.name
            if fname.startswith("id") and "-" in fname:
                # mini_vox flat structure: id10001-video-00001.wav
                spk_id = fname.split("-")[0]
                target_out_dir = out_root / user_dir.name / spk_id # Preserve split structure: out_root/train/id10001
            else:
                # Standard structure: user01/001.wav -> out_root/user01
                target_out_dir = out_root / user_dir.name
            
            os.makedirs(target_out_dir, exist_ok=True)
            tasks.append((str(w), str(target_out_dir), feature_type, n_mels))

        start_all = time.perf_counter()
        
        # Determine workers
        # workers arg: 0 -> auto
        final_workers = workers if workers > 0 else max(1, mp.cpu_count() - 1)
        
        if final_workers == 1:
            for i, t in enumerate(tasks, 1):
                name, shape, skipped = process_one(t)
                if skipped:
                    print(f"   [{i}/{len(tasks)}] ↷ {name}  skip")
                else:
                    print(f"   [{i}/{len(tasks)}] ✔ {name}  shape={shape}")
        else:
            ctx = mp.get_context("spawn")
            try:
                with cf.ProcessPoolExecutor(max_workers=final_workers, mp_context=ctx) as ex:
                    futures = [ex.submit(process_one, t) for t in tasks]
                    for i, fut in enumerate(cf.as_completed(futures), 1):
                        name, shape, skipped = fut.result()
                        if skipped:
                            print(f"   [{i}/{len(tasks)}] ↷ {name}  skip")
                        else:
                            print(f"   [{i}/{len(tasks)}] ✔ {name}  shape={shape}")
            except KeyboardInterrupt:
                raise
        cost_all = time.perf_counter() - start_all
        print(f"✅ 目录 {user_dir.name} 完成，用时 {cost_all:.2f}s")


if __name__ == "__main__":
    mp.freeze_support()
    main()