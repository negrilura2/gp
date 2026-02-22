"""
Voice Service Interface
Decouples backend from direct voice_engine implementation details.
This is the ONLY entry point the backend should use.
"""
import os
import logging
import numpy as np
import torch
from typing import List, Tuple, Optional, Dict, Any

from .config import (
    MODEL_PATH,
    TEMPLATE_PATH,
    DEFAULT_N_MELS,
    DEFAULT_THRESHOLD,
    DEFAULT_DEVICE,
    FEATURE_TYPE_MFCC_DELTA,
    DEFAULT_TEMPLATE_PATH
)
from .ecapa_tdnn import LightECAPA
from .dataset import (
    extract_feature_tensor,
    infer_feature_type_from_feat_dim,
    get_feature_dim
)

logger = logging.getLogger("voice_engine")

# ==========================================
# Helper Functions
# ==========================================

def load_templates(path=None):
    """Load voiceprint templates dictionary {user_id: embedding}"""
    path = path or TEMPLATE_PATH
    if not os.path.exists(path):
        # Return empty dict instead of raising error to allow first enrollment
        return {} 
    return np.load(path, allow_pickle=True).item()

def save_templates(templates, path=None):
    """Save voiceprint templates dictionary"""
    path = path or TEMPLATE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.save(path, templates)
    logger.info(f"Templates saved to {path}")

def cosine_score(a, b):
    """Compute cosine similarity between two vectors"""
    a = a / (np.linalg.norm(a) + 1e-9)
    b = b / (np.linalg.norm(b) + 1e-9)
    s = float(np.dot(a, b))
    if s > 1.0:
        s = 1.0
    elif s < -1.0:
        s = -1.0
    return s

def load_model(model_path=MODEL_PATH, device=None, feature_type=None, n_mels=DEFAULT_N_MELS):
    """Load the ECAPA-TDNN model"""
    if device is None:
        device = DEFAULT_DEVICE if torch.cuda.is_available() else "cpu"
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    state = torch.load(model_path, map_location=device)
    
    if feature_type is None:
        # Try to infer from model weights if possible
        w = state.get("layer1.conv.weight")
        if w is not None and w.ndim == 3:
            feat_dim_state = int(w.shape[1])
            feature_type = infer_feature_type_from_feat_dim(feat_dim_state, n_mels)
        else:
            feature_type = FEATURE_TYPE_MFCC_DELTA
            
    feat_dim = get_feature_dim(feature_type, n_mels)
    model = LightECAPA(feat_dim=feat_dim, emb_dim=192, n_speakers=None).to(device)
    model.load_state_dict(state, strict=False)
    model.eval()
    return model, device, feature_type

def extract_embedding(model, device, wav_path, feature_type=FEATURE_TYPE_MFCC_DELTA, n_mels=DEFAULT_N_MELS):
    """Extract embedding from a single wav file"""
    feat = extract_feature_tensor(wav_path, feature_type=feature_type, n_mels=n_mels, device=device)
    lengths = torch.tensor([feat.shape[2]], device=device)
    with torch.no_grad():
        emb = model(feat, lengths, return_embedding=True)
    emb = emb.detach().cpu().numpy()[0]
    return emb

# ==========================================
# VoiceService Class
# ==========================================

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
            
            # Infer feat_dim from model structure
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
            assert len(wav_paths) >= 1, "At least one wav file required for enrollment"
            
            embs = []
            for p in wav_paths:
                if not os.path.exists(p):
                    raise FileNotFoundError(f"Wav file not found: {p}")
                
                e = extract_embedding(
                    self.model, 
                    self.device, 
                    p, 
                    feature_type=self.feature_type, 
                    n_mels=self.n_mels
                )
                embs.append(e)

            user_template = np.mean(np.stack(embs, axis=0), axis=0)

            # Load existing templates
            templates = load_templates(TEMPLATE_PATH)
            templates[user_id] = user_template
            
            # Save updated templates
            save_templates(templates, TEMPLATE_PATH)
            
            logger.info(f"Enrolled user {user_id} with {len(wav_paths)} samples.")
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
            if not os.path.exists(wav_path):
                raise FileNotFoundError(f"Wav file not found: {wav_path}")

            # Extract embedding
            emb = extract_embedding(
                self.model, 
                self.device, 
                wav_path, 
                feature_type=self.feature_type, 
                n_mels=self.n_mels
            )

            # Load templates
            templates = load_templates(TEMPLATE_PATH)
            if not templates:
                return {"status": "reject", "score": 0.0, "speaker": None, "message": "No enrolled users"}

            # Compare against all templates
            best_spk, best_score = None, -1.0
            
            for spk, tmpl in templates.items():
                # Support multi-shot templates (list of embeddings) or single (mean embedding)
                if isinstance(tmpl, np.ndarray) and tmpl.ndim == 1:
                    s = cosine_score(emb, tmpl)
                elif isinstance(tmpl, (list, np.ndarray)):
                    # If template is a list of embeddings, take max score
                    scores = [cosine_score(emb, t) for t in tmpl]
                    s = max(scores) if scores else -1.0
                else:
                    s = cosine_score(emb, tmpl)

                if s > best_score:
                    best_score = s
                    best_spk = spk

            result = "ACCEPT" if best_score >= thr else "REJECT"
            logger.info(f"Verification: {wav_path} -> Best match: {best_spk} ({best_score:.4f}) => {result}")
            
            return {
                "status": "success",
                "result": result,
                "best_score": float(best_score),
                "best_speaker": best_spk,
                "threshold": thr
            }

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    # Simple CLI for testing
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m voice_engine.service [enroll|verify] ...")
        sys.exit(1)
        
    cmd = sys.argv[1]
    svc = VoiceService.get_instance()
    
    if cmd == "enroll":
        if len(sys.argv) < 4:
            print("Usage: enroll <user_id> <wav1> [wav2 ...]")
            sys.exit(1)
        uid = sys.argv[2]
        wavs = sys.argv[3:]
        print(svc.enroll(uid, wavs))
        
    elif cmd == "verify":
        if len(sys.argv) < 3:
            print("Usage: verify <wav_path> [threshold]")
            sys.exit(1)
        wav = sys.argv[2]
        th = float(sys.argv[3]) if len(sys.argv) > 3 else None
        print(svc.verify(wav, th))
    else:
        print(f"Unknown command: {cmd}")
