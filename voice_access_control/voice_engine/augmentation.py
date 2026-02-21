import numpy as np
import soundfile as sf
import os
import random
import glob

def add_noise(y, snr_db, rng=None, noise_y=None):
    """
    Add noise to a signal at a specified SNR.
    
    Args:
        y (np.ndarray): Clean signal.
        snr_db (float): Signal-to-Noise Ratio in dB. If None, return original.
        rng (np.random.RandomState): Random number generator. If None, use np.random.
        noise_y (np.ndarray): Noise signal. If None, use white noise.
        
    Returns:
        np.ndarray: Noisy signal.
    """
    if snr_db is None:
        return y
        
    if rng is None:
        rng = np.random
        
    signal_power = np.mean(y ** 2)
    if signal_power <= 1e-12:
        return y
        
    snr_linear = 10 ** (snr_db / 10.0)
    noise_power = signal_power / snr_linear
    
    if noise_y is None:
        # White noise
        noise = rng.normal(0.0, np.sqrt(noise_power), size=y.shape)
        return y + noise
        
    # Real noise logic:
    # 1. Ensure noise is long enough by tiling
    # 2. Random crop
    # 3. Normalize noise segment power to 1 (so we can scale it to sqrt(noise_power))
    
    if len(noise_y) < len(y):
        rep = int(np.ceil(len(y) / len(noise_y)))
        src = np.tile(noise_y, rep)[: len(y)]
    else:
        start = rng.randint(0, len(noise_y) - len(y) + 1)
        src = noise_y[start : start + len(y)]
    
    src_power = np.mean(src ** 2)
    if src_power > 1e-12:
        src = src / np.sqrt(src_power)  # Normalize to unit power
    
    noise = src * np.sqrt(noise_power)
    
    return y + noise

class NoiseAugmentor:
    def __init__(self, noise_dir, snr_min=0, snr_max=15, sample_rate=16000):
        self.noise_dir = noise_dir
        self.snr_min = snr_min
        self.snr_max = snr_max
        self.sample_rate = sample_rate
        self.noises = []
        self._load_noises()

    def _load_noises(self):
        if not os.path.exists(self.noise_dir):
            print(f"Warning: Noise dir {self.noise_dir} not found.")
            return
            
        files = glob.glob(os.path.join(self.noise_dir, "*.wav"))
        print(f"Loading {len(files)} noise files from {self.noise_dir}...")
        for f in files:
            try:
                y, sr = sf.read(f)
                if y.ndim > 1:
                    y = y.mean(axis=1) # mix to mono
                if sr != self.sample_rate:
                    # simplistic resample if needed, but ideally offline
                    # using scipy.signal.resample
                    import scipy.signal
                    num = int(len(y) * self.sample_rate / sr)
                    y = scipy.signal.resample(y, num)
                self.noises.append(y)
            except Exception as e:
                print(f"Error loading {f}: {e}")
        print(f"Loaded {len(self.noises)} valid noise clips.")

    def __call__(self, wav):
        if not self.noises:
            return wav
            
        # 50% chance to add noise? Or always? Usually always if 'noise training' is the goal,
        # but typically we want some clean data too. Let's say 80% chance.
        if random.random() > 0.8:
            return wav

        noise_idx = random.randint(0, len(self.noises) - 1)
        noise = self.noises[noise_idx]
        snr = random.uniform(self.snr_min, self.snr_max)
        
        return add_noise(wav, snr, noise_y=noise)
