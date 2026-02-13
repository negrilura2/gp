import argparse
import os
import sys
import shutil
from tqdm import tqdm

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import RAW_DIR

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source_dir", default=os.path.join(RAW_DIR, "mini_vox", "train"))
    parser.add_argument("--target_root", default=str(RAW_DIR))
    args = parser.parse_args()

    source_dir = args.source_dir
    target_root = args.target_root
    files = [f for f in os.listdir(source_dir) if f.endswith(".wav")]
    print(f"Found {len(files)} wav files")
    for fname in tqdm(files):
        speaker_id = fname.split("-")[0]
        spk_dir = os.path.join(target_root, speaker_id)
        os.makedirs(spk_dir, exist_ok=True)
        src_path = os.path.join(source_dir, fname)
        dst_path = os.path.join(spk_dir, fname)
        shutil.copy(src_path, dst_path)
    print("✅ 训练数据已按说话人分类完成！")


if __name__ == "__main__":
    main()
