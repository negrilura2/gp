"""
Voice Service Interface
Decouples backend from direct voice_engine implementation details.
This is the ONLY entry point the backend should use.
"""
import os
import logging
from typing import List, Tuple, Optional, Dict, Any

from .config import (
    MODEL_PATH,
    TEMPLATE_PATH,
    DEFAULT_N_MELS,
    DEFAULT_THRESHOLD,
    DEFAULT_DEVICE
)
from .enroll import enroll as _engine_enroll, load_model
from .verify import verify as _engine_verify

logger = logging.getLogger("voice_engine")

class VoiceService:
    """
    Singleton service wrapper for Voice Engine.
    Handles model loading, enrollment, and verification.
    """
    _instance = None
    
    def __init__(self, model_path: str = None, device: str = None):
        self.model_path = model_path or MODEL_PATH
        self.device = device or DEFAULT_DEVICE
        self.model = None
        self.feature_type = None
        self.n_mels = DEFAULT_N_MELS
        self.feat_dim = None
        self._load()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        """Internal load method."""
        logger.info(f"Loading Voice Engine Model from {self.model_path} on {self.device}")
        try:
            self.model, self.device, self.feature_type = load_model(
                model_path=self.model_path,
                device=self.device,
                n_mels=self.n_mels
            )
            # Infer feat_dim from model structure if possible, or use config default
            # Currently load_model returns (model, device, feature_type)
            # We can get feat_dim from the first layer
            if hasattr(self.model, 'layer1') and hasattr(self.model.layer1, 'conv'):
                self.feat_dim = self.model.layer1.conv.weight.shape[1]
            
            logger.info(f"Model loaded successfully. Feature Type: {self.feature_type}, Dim: {self.feat_dim}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

    def enroll(self, user_id: str, wav_paths: List[str]) -> Dict[str, Any]:
        """
        Enroll a user with a list of wav files.
        """
        try:
            _engine_enroll(
                user_id=user_id,
                wav_paths=wav_paths,
                model_path=self.model_path, # Although engine_enroll loads model internally, passing it for consistency
                # Optimisation: Refactor engine_enroll to accept loaded model instance to avoid reload
                # For now, we rely on existing implementation but we should improve this.
                # Actually, looking at enroll.py, it calls load_model. 
                # Ideally we should pass self.model to avoid reloading.
                # But current enroll signature is: 
                # enroll(user_id, wav_paths, model_path=..., template_path=..., ...)
                # It doesn't accept model instance. 
                # TODO: Refactor enroll.py to accept model instance.
            )
            return {"status": "success", "user_id": user_id, "wav_count": len(wav_paths)}
        except Exception as e:
            logger.error(f"Enrollment failed for {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def verify(self, wav_path: str, threshold: float = None) -> Dict[str, Any]:
        """
        Verify a wav file against enrolled templates.
        """
        thr = threshold if threshold is not None else DEFAULT_THRESHOLD
        
        try:
            # We pass self.model to verify to use the pre-loaded instance (Efficiency!)
            best_spk, best_score, result = _engine_verify(
                wav_path=wav_path,
                threshold=thr,
                model=self.model,
                device=self.device,
                feature_type=self.feature_type,
                n_mels=self.n_mels
            )
            
            return {
                "status": "success",
                "predicted_user": best_spk,
                "score": float(best_score),
                "result": result,
                "threshold": thr
            }
        except Exception as e:
            logger.error(f"Verification failed for {wav_path}: {e}")
            return {"status": "error", "error": str(e)}

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_path": self.model_path,
            "device": self.device,
            "feature_type": self.feature_type,
            "n_mels": self.n_mels,
            "feat_dim": self.feat_dim
        }
