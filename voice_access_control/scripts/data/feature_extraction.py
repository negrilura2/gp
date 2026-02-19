import argparse
import os
import sys
import time
import multiprocessing as mp
import concurrent.futures as cf
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
from voice_engine.features import extract_feature_numpy

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_root", default=str(PROCESSED_DIR))
    parser.add_argument("--out_root", default=str(FEATURES_DIR))
    parser.add_argument("--feature_type", choices=[FEATURE_TYPE_MFCC, FEATURE_TYPE_MFCC_DELTA, FEATURE_TYPE_LOGMEL], default=FEATURE_TYPE_MFCC_DELTA)
    parser.add_argument("--n_mels", type=int, default=DEFAULT_N_MELS)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--feature_subdir", default="")
    args = parser.parse_args()

    in_root = Path(args.in_root)
    feature_subdir = args.feature_subdir or args.feature_type
    out_root = Path(args.out_root) / feature_subdir
    if not in_root.exists():
        raise FileNotFoundError(in_root)

    for user_dir in in_root.iterdir():
        if not user_dir.is_dir():
            continue
        wav_list = [w for w in user_dir.iterdir() if w.suffix.lower() == ".wav"]
        print(f"\n🎤 正在提取用户 {user_dir.name} ，共 {len(wav_list)} 条")
        out_dir = out_root / user_dir.name
        os.makedirs(out_dir, exist_ok=True)
        tasks = [(str(w), str(out_dir), args.feature_type, args.n_mels) for w in wav_list]
        start_all = time.perf_counter()
        workers = args.workers if args.workers > 0 else max(1, mp.cpu_count() - 1)
        if workers == 1:
            for i, t in enumerate(tasks, 1):
                name, shape, skipped = process_one(t)
                if skipped:
                    print(f"   [{i}/{len(tasks)}] ↷ {name}  skip")
                else:
                    print(f"   [{i}/{len(tasks)}] ✔ {name}  shape={shape}")
        else:
            ctx = mp.get_context("spawn")
            try:
                with cf.ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as ex:
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
        print(f"✅ 用户 {user_dir.name} 完成，用时 {cost_all:.2f}s")


if __name__ == "__main__":
    mp.freeze_support()
    main()
