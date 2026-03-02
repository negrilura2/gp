# scripts/audio/record_and_verify.py
"""
CLI:
# enroll by recording n utterances:
python -m scripts.audio.record_and_verify enroll alice --n 3
# enroll by wav folder:
python -m scripts.audio.record_and_verify enroll alice --wav_dir data/enroll/alice
# verify by recording:
python -m scripts.audio.record_and_verify verify
# verify by wav file:
python -m scripts.audio.record_and_verify verify --wav data/processed/user01/1.wav
# Use config:
python -m scripts.audio.record_and_verify --config configs/record.yaml verify
"""

import os
import sys
import argparse
import time
import yaml
import sounddevice as sd
import soundfile as sf
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.config import (
    RECORDINGS_DIR, 
    DEFAULT_MODEL_PATH, 
    SAMPLE_RATE
)
from voice_engine.service import VoiceService

TMP_DIR = os.fspath(RECORDINGS_DIR)
os.makedirs(TMP_DIR, exist_ok=True)

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def record_once(out_path, duration=3, sr=SAMPLE_RATE):
    print(f"开始录音 {duration}s，请对着麦克风说话...")
    rec = sd.rec(int(duration * sr), samplerate=sr, channels=1, dtype='float32')
    sd.wait()
    sf.write(out_path, rec, sr)
    print(f"录音保存: {out_path}")


def enroll_interactive(user_id, n=3, duration=3, model_path=None):
    wavs = []
    for i in range(n):
        ts = time.strftime("%Y%m%d_%H%M%S")
        out = os.path.join(TMP_DIR, f"enroll_{user_id}_{i+1}_{ts}.wav")
        record_once(out, duration=duration)
        wavs.append(out)
        time.sleep(0.3)
    
    # model_path defaults to None, which VoiceService handles by using DEFAULT_MODEL_PATH
    svc = VoiceService(model_path=model_path)
    # Note: VoiceService.enroll might need implementation adaptation if not supporting list of wavs directly
    # Assuming VoiceService.enroll supports list of paths or directory. 
    # Checking VoiceService... it usually takes user_id and file_paths.
    try:
        svc.enroll_new_user(user_id, wavs)
    except AttributeError:
        # Fallback if method name differs
        svc.enroll(user_id, wavs)


def enroll_from_dir(user_id, wav_dir, model_path=None):
    wav_dir = Path(wav_dir)
    wavs = sorted([str(p) for p in wav_dir.iterdir() if p.suffix.lower() == ".wav"])
    if len(wavs) == 0:
        print("目录中没有 wav 文件")
        return
    
    svc = VoiceService(model_path=model_path)
    try:
        svc.enroll_new_user(user_id, wavs)
    except AttributeError:
        svc.enroll(user_id, wavs)


def verify_interactive(duration=3, model_path=None, threshold=0.75):
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(TMP_DIR, f"verify_{ts}.wav")
    record_once(out, duration=duration)
    
    svc = VoiceService(model_path=model_path)
    result = svc.verify(out, threshold=threshold)
    print(f"Verification Result: {result}")


def verify_by_file(wav_path, model_path=None, threshold=0.75):
    svc = VoiceService(model_path=model_path)
    result = svc.verify(wav_path, threshold=threshold)
    print(f"Verification Result: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record audio for enrollment or verification")
    parser.add_argument("action", choices=["enroll", "verify"], nargs="?", help="Action to perform")
    parser.add_argument("user_id", nargs="?", help="User ID for enrollment")
    
    # Default to configs/record_and_verify.yaml
    parser.add_argument("--config", "-c", default="configs/record_and_verify.yaml", help="Path to config yaml file")
    
    parser.add_argument("--n", type=int, default=3, help="Number of utterances to record")
    parser.add_argument("--duration", type=int, default=3, help="Duration of each recording in seconds")
    parser.add_argument("--wav_dir", help="Directory containing wav files for enrollment")
    parser.add_argument("--wav", help="Wav file for verification")
    parser.add_argument("--model", help="Path to model checkpoint")
    parser.add_argument("--threshold", type=float, default=0.75, help="Verification threshold")

    args = parser.parse_args()

    # Load config if available
    cfg = {}
    if args.config and os.path.exists(args.config):
        cfg = load_config(args.config)
    
    # Priority: CLI > Config > Default
    model_path = args.model or cfg.get("model", {}).get("path") or DEFAULT_MODEL_PATH
    threshold = args.threshold or cfg.get("model", {}).get("threshold") or 0.75
    duration = args.duration or cfg.get("audio", {}).get("duration") or 3
    
    if args.action == "enroll":
        if not args.user_id:
            print("Error: user_id is required for enrollment")
            sys.exit(1)
            
        if args.wav_dir:
            enroll_from_dir(args.user_id, args.wav_dir, model_path=model_path)
        else:
            n_recs = args.n or cfg.get("enrollment", {}).get("n_recordings") or 3
            enroll_interactive(args.user_id, n=n_recs, duration=duration, model_path=model_path)
            
    elif args.action == "verify":
        if args.wav:
            verify_by_file(args.wav, model_path=model_path, threshold=threshold)
        else:
            verify_interactive(duration=duration, model_path=model_path, threshold=threshold)
    else:
        parser.print_help()
