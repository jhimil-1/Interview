import numpy as np
from scipy import signal
import pyaudio

class AudioProcessor:
    @staticmethod
    def detect_silence(audio_data, threshold=500, chunk_size=1024):
        """Detect if audio contains silence"""
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        return np.abs(audio_array).mean() < threshold
    
    @staticmethod
    def apply_noise_reduction(audio_data):
        """Apply basic noise reduction"""
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        # Simple low-pass filter
        b, a = signal.butter(4, 0.1)
        filtered = signal.filtfilt(b, a, audio_array)
        return filtered.astype(np.int16).tobytes()

