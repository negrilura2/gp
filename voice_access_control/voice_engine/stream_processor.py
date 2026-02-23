"""
Streaming Audio Processor
Handles buffering, VAD (Voice Activity Detection), and triggering recognition.
"""
import collections
import logging
import webrtcvad
import numpy as np
import io
import wave

logger = logging.getLogger("voice_engine.stream")

class AudioBuffer:
    def __init__(self, sample_rate=16000, frame_duration_ms=30, padding_duration_ms=300):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000) * 2 # 2 bytes per sample (16-bit)
        self.vad = webrtcvad.Vad(2) # Mode 2: Aggressive
        
        self.buffer = bytearray()
        self.ring_buffer = collections.deque(maxlen=padding_duration_ms // frame_duration_ms)
        self.triggered = False
        self.voiced_frames = []
        
    def process(self, chunk: bytes) -> list[bytes]:
        """
        Process a raw audio chunk (PCM 16-bit Mono).
        Returns a list of complete voice segments (wav bytes) if speech ended.
        """
        self.buffer.extend(chunk)
        
        segments = []
        while len(self.buffer) >= self.frame_size:
            frame = self.buffer[:self.frame_size]
            self.buffer = self.buffer[self.frame_size:]
            
            is_speech = False
            try:
                is_speech = self.vad.is_speech(frame, self.sample_rate)
            except Exception:
                pass # Ignore VAD errors on bad frames

            if not self.triggered:
                self.ring_buffer.append((frame, is_speech))
                num_voiced = len([f for f, s in self.ring_buffer if s])
                if num_voiced > 0.9 * self.ring_buffer.maxlen:
                    self.triggered = True
                    self.voiced_frames.extend([f for f, s in self.ring_buffer])
                    self.ring_buffer.clear()
            else:
                self.voiced_frames.append(frame)
                self.ring_buffer.append((frame, is_speech))
                num_unvoiced = len([f for f, s in self.ring_buffer if not s])
                if num_unvoiced > 0.9 * self.ring_buffer.maxlen:
                    self.triggered = False
                    # Speech ended, flush voiced frames
                    wav_data = self._create_wav(self.voiced_frames)
                    segments.append(wav_data)
                    self.voiced_frames = []
                    self.ring_buffer.clear()
                    
        return segments

    def _create_wav(self, frames):
        """Convert PCM frames to WAV bytes"""
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
        return buffer.getvalue()

    def flush(self):
        """Force flush remaining frames as a segment"""
        if self.voiced_frames:
            wav = self._create_wav(self.voiced_frames)
            self.voiced_frames = []
            self.triggered = False
            return [wav]
        return []
