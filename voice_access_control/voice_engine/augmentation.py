import numpy as np

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
        
    # Real noise
    if len(noise_y) < len(y):
        rep = int(np.ceil(len(y) / len(noise_y)))
        src = np.tile(noise_y, rep)[: len(y)]
    else:
        start = rng.randint(0, len(noise_y) - len(y) + 1)
        src = noise_y[start : start + len(y)]
        
    noise = src * np.sqrt(noise_power)
    
    return y + noise
