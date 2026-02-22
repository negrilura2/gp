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

from scripts import RECORDINGS_DIR, MODELS_DIR
from voice_engine.service import VoiceService


SAMPLE_RATE = 16000
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
    
    svc = VoiceService(model_path=model_path) if model_path else VoiceService.get_instance()
    svc.enroll(user_id, wavs)


def enroll_from_dir(user_id, wav_dir, model_path=None):
    wav_dir = Path(wav_dir)
    wavs = sorted([str(p) for p in wav_dir.iterdir() if p.suffix.lower() == ".wav"])
    if len(wavs) == 0:
        print("目录中没有 wav 文件")
        return
    
    svc = VoiceService(model_path=model_path) if model_path else VoiceService.get_instance()
    svc.enroll(user_id, wavs)


def verify_interactive(duration=3, model_path=None, threshold=0.75):
    ts = time.strftime("%Y%m%d_%H%M%S")
    out = os.path.join(TMP_DIR, f"verify_{ts}.wav")
    record_once(out, duration=duration)
    
    svc = VoiceService(model_path=model_path) if model_path else VoiceService.get_instance()
    svc.verify(out, threshold=threshold)


def verify_by_file(wav_path, model_path=None, threshold=0.75):
    svc = VoiceService(model_path=model_path) if model_path else VoiceService.get_instance()
    svc.verify(wav_path, threshold=threshold)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", "-c", help="Path to config yaml file")
    
    sub = parser.add_subparsers(dest="cmd")

    p_en = sub.add_parser("enroll")
    p_en.add_argument("user_id")
    p_en.add_argument("--n", type=int, default=None, help="录音条数（交互模式）")
    p_en.add_argument("--wav_dir", type=str, default=None, help="若提供 wav_dir, 从文件夹导入")
    p_en.add_argument("--model_path", type=str, default=None)

    p_v = sub.add_parser("verify")
    p_v.add_argument("--wav", type=str, default=None, help="若提供 wav 文件则使用该文件，否则录音")
    p_v.add_argument("--threshold", type=float, default=None)
    p_v.add_argument("--model_path", type=str, default=None)

    args = parser.parse_args()
    
    cfg = {}
    if args.config:
        if os.path.exists(args.config):
            cfg = load_config(args.config)
        else:
            print(f"Config file not found: {args.config}")
            return

    # Defaults
    def_n = cfg.get("enrollment", {}).get("n_utterances", 3)
    def_duration = cfg.get("audio", {}).get("duration", 3)
    def_threshold = cfg.get("verification", {}).get("threshold", 0.75)
    def_model_path = cfg.get("verification", {}).get("model_path") or cfg.get("model", {}).get("path")

    if args.cmd == "enroll":
        n = args.n if args.n is not None else def_n
        model_path = args.model_path or def_model_path
        
        if args.wav_dir:
            enroll_from_dir(args.user_id, args.wav_dir, model_path=model_path)
        else:
            enroll_interactive(args.user_id, n=n, duration=def_duration, model_path=model_path)
            
    elif args.cmd == "verify":
        threshold = args.threshold if args.threshold is not None else def_threshold
        model_path = args.model_path or def_model_path
        
        if args.wav:
            verify_by_file(args.wav, model_path=model_path, threshold=threshold)
        else:
            verify_interactive(duration=def_duration, model_path=model_path, threshold=threshold)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
