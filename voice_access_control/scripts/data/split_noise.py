import os
import soundfile as sf
import math
import numpy as np

NOISE_DIR = r"d:\traepg\gp\voice_access_control\data\noise"
SRC_FILE = os.path.join(NOISE_DIR, "street1.wav")
N_PARTS = 9

def split_noise():
    if not os.path.exists(SRC_FILE):
        print(f"Error: {SRC_FILE} not found.")
        return

    print(f"Loading {SRC_FILE}...")
    y, sr = sf.read(SRC_FILE)
    
    total_samples = len(y)
    part_len = math.ceil(total_samples / N_PARTS)
    
    print(f"Total samples: {total_samples}, SR: {sr}")
    print(f"Splitting into {N_PARTS} parts, approx {part_len/sr:.2f}s each.")

    for i in range(N_PARTS):
        start = i * part_len
        end = min((i + 1) * part_len, total_samples)
        part = y[start:end]
        
        out_name = f"street1_part{i+1}.wav"
        out_path = os.path.join(NOISE_DIR, out_name)
        
        sf.write(out_path, part, sr)
        print(f"Saved {out_path}")

if __name__ == "__main__":
    split_noise()
