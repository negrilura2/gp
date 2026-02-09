# scripts/record_and_verify.py
"""
CLI:
# enroll by recording n utterances:
python -m scripts.record_and_verify enroll alice --n 3
# enroll by wav folder:
python -m scripts.record_and_verify enroll alice --wav_dir data/enroll/alice
# verify by recording:
python -m scripts.record_and_verify verify
# verify by wav file:
python -m scripts.record_and_verify verify --wav data/processed/user01/1.wav
"""

import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import argparse
import time
import sounddevice as sd
import soundfile as sf
from pathlib import Path
from model.enroll import enroll as model_enroll
from model.verify_demo import verify as model_verify


SAMPLE_RATE = 16000
TMP_DIR = "data/recordings"
os.makedirs(TMP_DIR, exist_ok=True)


def record_once(out_path, duration=3, sr=SAMPLE_RATE):
    print(f"开始录音 {duration}s，请对着麦克风说话...")
    rec = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
    sd.wait()
    sf.write(out_path, rec, sr)
    print(f"录音保存: {out_path}")


def enroll_interactive(user_id, n=3, duration=3):
    wavs = []
    for i in range(n):
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(TMP_DIR, f"enroll_{user_id}_{i+1}_{ts}.wav")
        record_once(out, duration=duration)
        wavs.append(out)
        time.sleep(0.3)
    model_enroll(user_id, wavs)


def enroll_from_dir(user_id, wav_dir):
    wav_dir = Path(wav_dir)
    wavs = sorted([str(p) for p in wav_dir.iterdir() if p.suffix.lower() == ".wav"])
    if len(wavs) == 0:
        print("目录中没有 wav 文件")
        return
    model_enroll(user_id, wavs)


def verify_interactive(duration=3, model_path=None, threshold=0.75):
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(TMP_DIR, f"verify_{ts}.wav")
    record_once(out, duration=duration)
    model_verify(out, model_path=model_path or "models/ecapa_best.pth", threshold=threshold)


def verify_by_file(wav_path, model_path=None, threshold=0.75):
    model_verify(wav_path, model_path=model_path or "models/ecapa_best.pth", threshold=threshold)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    p_en = sub.add_parser("enroll")
    p_en.add_argument("user_id")
    p_en.add_argument("--n", type=int, default=3, help="录音条数（交互模式）")
    p_en.add_argument("--wav_dir", type=str, default=None, help="若提供 wav_dir, 从文件夹导入")

    p_v = sub.add_parser("verify")
    p_v.add_argument("--wav", type=str, default=None, help="若提供 wav 文件则使用该文件，否则录音")
    p_v.add_argument("--threshold", type=float, default=0.75)

    args = parser.parse_args()
    if args.cmd == "enroll":
        if args.wav_dir:
            enroll_from_dir(args.user_id, args.wav_dir)
        else:
            enroll_interactive(args.user_id, n=args.n)
    elif args.cmd == "verify":
        if args.wav:
            verify_by_file(args.wav, threshold=args.threshold)
        else:
            verify_interactive(threshold=args.threshold)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
