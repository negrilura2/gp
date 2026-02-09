import sounddevice as sd
from scipy.io.wavfile import write
import os

SAMPLE_RATE = 16000
DURATION = 3
CHANNELS = 1

# ⭐ 获取项目根目录（scripts 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def record(user_id: str, utt_id: str):
    print("🎤 开始录音，请清晰朗读口令：『开门验证』")
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype='int16'
    )
    sd.wait()
    print("✅ 录音结束")

    # ⭐ 拼接到 项目根目录/data/raw/user_id
    save_dir = os.path.join(BASE_DIR, "data", "raw", user_id)
    os.makedirs(save_dir, exist_ok=True)

    save_path = os.path.join(save_dir, f"{utt_id}.wav")
    write(save_path, SAMPLE_RATE, audio)

    print(f"💾 音频已保存至: {save_path}")

if __name__ == "__main__":
    user = input("请输入用户ID（如 user01）：")
    utt = input("请输入语音编号（如 001）：")
    record(user, utt)
