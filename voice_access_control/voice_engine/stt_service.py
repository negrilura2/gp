"""
STT Service using Faster-Whisper.
Provides speech-to-text transcription capabilities.
"""
import os
import logging
import gc
import numpy as np
from typing import Union, BinaryIO
from faster_whisper import WhisperModel

logger = logging.getLogger("voice_engine.stt")

class STTService:
    _instance = None

    def __init__(self, model_size: str = "tiny", device: str = "auto", compute_type: str = "default"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        self._cuda_failed = False  # Prevent infinite fallback loops
        self._load()

    @classmethod
    def get_instance(cls, model_size="tiny", device="auto"):
        if cls._instance is None:
            cls._instance = cls(model_size, device)
        return cls._instance

    def _check_cuda(self):
        """Robust check for CUDA availability"""
        try:
            import torch
            if not torch.cuda.is_available():
                return False
            # Trigger actual CUDA initialization
            torch.zeros(1).cuda()
            return True
        except Exception:
            return False

    def _load(self):
        """Load Faster-Whisper model"""
        try:
            # Determine device
            if self.device == "auto":
                if self._check_cuda():
                    self.device = "cuda"
                else:
                    self.device = "cpu"
            
            # If we already failed CUDA once, force CPU
            if self._cuda_failed:
                self.device = "cpu"

            # For CPU, force int8 to avoid float16 errors on some CPUs
            if self.device == "cpu":
                self.compute_type = "int8"

            logger.info(f"Loading Faster-Whisper ({self.model_size}) on {self.device}...")
            
            try:
                self.model = WhisperModel(
                    self.model_size, 
                    device=self.device, 
                    compute_type=self.compute_type,
                    cpu_threads=4 # Limit threads to prevent resource exhaustion
                )
            except Exception as e:
                # Catch initialization errors (like DLL missing)
                if self.device == "cuda" and not self._cuda_failed:
                    logger.warning(f"CUDA init failed ({e}), falling back to CPU...")
                    self._cuda_failed = True
                    self.device = "cpu"
                    self._load() # Recursive retry once
                    return
                else:
                    raise e

            logger.info(f"Faster-Whisper loaded successfully on {self.device}.")
        except Exception as e:
            logger.error(f"Failed to load Faster-Whisper: {e}")
            raise

    def transcribe(self, audio: Union[str, BinaryIO, np.ndarray], beam_size: int = 5) -> dict:
        """
        Transcribe audio to text.
        Args:
            audio: Path to file, file-like object, or numpy array
        """
        if not self.model:
            raise RuntimeError("STT Model not initialized")
            
        # Only check path existence if it's a string
        if isinstance(audio, str):
            if not os.path.exists(audio):
                raise FileNotFoundError(f"Audio file not found: {audio}")

        try:
            # Note: transcribe returns a generator
            # Force language to Chinese ('zh') to avoid random Thai/English
            # Use initial_prompt to guide Simplified Chinese output
            segments, info = self.model.transcribe(
                audio, 
                beam_size=beam_size,
                language="zh",
                initial_prompt="请使用简体中文回复。这是智能家居的语音指令，例如：开门、关灯、报警。"
            )
            
            # Force consumption of the generator to catch any runtime errors (like CUDA errors)
            seg_list = []
            full_text = []
            for segment in segments:
                seg_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text
                })
                full_text.append(segment.text)
            
            # Cleanup memory
            del segments, info
            if self.device == "cuda":
                import torch
                torch.cuda.empty_cache()
            gc.collect()
            
            return {
                "text": "".join(full_text),
                "segments": seg_list,
                "language": "zh"
            }
        except Exception as e:
            # Runtime fallback
            is_cuda_error = "cublas" in str(e).lower() or "library" in str(e).lower() or "cuda" in str(e).lower()
            
            if is_cuda_error and self.device == "cuda" and not self._cuda_failed:
                logger.warning(f"CUDA runtime error ({e}), switching to CPU forever...")
                self._cuda_failed = True
                self.device = "cpu"
                # Reload model on CPU
                self._load()
                # Retry transcription
                return self.transcribe(audio, beam_size)
            else:
                logger.error(f"Transcription failed: {e}")
                raise
