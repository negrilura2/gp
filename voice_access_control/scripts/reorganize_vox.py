import os
import shutil
from tqdm import tqdm

source_dir = "data/raw/mini_vox/train"
target_root = "data/raw"

files = [f for f in os.listdir(source_dir) if f.endswith(".wav")]

print(f"Found {len(files)} wav files")

for fname in tqdm(files):
    speaker_id = fname.split("-")[0]   # 例如 id10012
    spk_dir = os.path.join(target_root, speaker_id)
    os.makedirs(spk_dir, exist_ok=True)

    src_path = os.path.join(source_dir, fname)
    dst_path = os.path.join(spk_dir, fname)

    shutil.copy(src_path, dst_path)

print("✅ 训练数据已按说话人分类完成！")
