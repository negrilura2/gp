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
from python_speech_features import mfcc, delta, logfbank

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import PROCESSED_DIR, FEATURES_DIR

SAMPLE_RATE = 16000
N_MFCC = 13

def extract_mfcc(wav_path, with_delta=True):
    y, sr = sf.read(wav_path)

    # 转单声道
    if len(y.shape) > 1:
        y = y.mean(axis=1)

    # 保证采样率 16k
    if sr != SAMPLE_RATE:
        raise ValueError(f"采样率不是16k: {wav_path}")

    # MFCC
    mfcc_feat = mfcc(
        y,
        samplerate=SAMPLE_RATE,
        numcep=N_MFCC,
        winlen=0.025,
        winstep=0.01,
        nfft=512
    )

    if not with_delta:
        return mfcc_feat

    d1 = delta(mfcc_feat, 2)
    d2 = delta(d1, 2)
    return np.hstack([mfcc_feat, d1, d2])


def extract_logmel(wav_path, n_mels=40):
    y, sr = sf.read(wav_path)
    if len(y.shape) > 1:
        y = y.mean(axis=1)
    if sr != SAMPLE_RATE:
        raise ValueError(f"采样率不是16k: {wav_path}")
    feat = logfbank(
        y,
        samplerate=SAMPLE_RATE,
        nfilt=n_mels,
        winlen=0.025,
        winstep=0.01,
        nfft=512,
    )
    return feat


def process_one(args):
    wav_path, out_dir, feature_type, n_mels = args
    out_path = os.path.join(out_dir, f"{Path(wav_path).stem}.npy")
    if os.path.exists(out_path):
        return os.path.basename(wav_path), None, True
    if feature_type == "mfcc":
        feat = extract_mfcc(wav_path, with_delta=False)
    elif feature_type == "logmel":
        feat = extract_logmel(wav_path, n_mels=n_mels)
    else:
        feat = extract_mfcc(wav_path, with_delta=True)
    np.save(out_path, feat)
    return os.path.basename(wav_path), feat.shape, False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--in_root", default=str(PROCESSED_DIR))
    parser.add_argument("--out_root", default=str(FEATURES_DIR))
    parser.add_argument("--feature_type", choices=["mfcc", "mfcc_delta", "logmel"], default="mfcc_delta")
    parser.add_argument("--n_mels", type=int, default=40)
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
