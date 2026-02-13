import argparse
import os
import sys
from pathlib import Path
import sounddevice as sd
from scipy.io.wavfile import write

SAMPLE_RATE = 16000
DURATION = 3
CHANNELS = 1

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import RAW_DIR

def record(user_id: str, utt_id: str, duration=DURATION):
    print("🎤 开始录音，请清晰朗读口令：『开门验证』")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16'
    )
    sd.wait()
    print("✅ 录音结束")

    save_dir = Path(RAW_DIR) / user_id
    os.makedirs(save_dir, exist_ok=True)

    save_path = save_dir / f"{utt_id}.wav"
    write(os.fspath(save_path), SAMPLE_RATE, audio)

    print(f"💾 音频已保存至: {save_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user_id", type=str, default=None)
    parser.add_argument("--utt_id", type=str, default=None)
    parser.add_argument("--duration", type=int, default=DURATION)
    args = parser.parse_args()

    user = args.user_id or input("请输入用户ID（如 user01）：")
    utt = args.utt_id or input("请输入语音编号（如 001）：")
    record(user, utt, duration=args.duration)
