"""
Voice Service Interface
Decouples backend from direct voice_engine implementation details.
This is the ONLY entry point the backend should use.
"""
import os
import logging
import json
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
    DEFAULT_TEMPLATE_PATH,
    EMBEDDING_DIM
)
from .ecapa_tdnn import LightECAPA
from .dataset import (
    extract_feature_tensor,
    infer_feature_type_from_feat_dim,
    get_feature_dim
)
from .vector_store import VectorStore

logger = logging.getLogger("voice_engine")

# ==========================================
# Helper Functions
# ==========================================

def load_templates(path=None):
    """Load voiceprint templates dictionary {user_id: embedding}"""
    # Backward compatibility: Try loading from .npy if VectorStore fails or is empty?
    # For now, we rely on VectorStore migration.
    # But to keep code safe, we can leave this helper if needed by other modules,
    # though VoiceService will use VectorStore.
    path = path or TEMPLATE_PATH
    if not os.path.exists(path):
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

    # Try to load metadata
    meta_path = os.path.splitext(model_path)[0] + ".json"
    meta_cfg = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                meta_cfg = json.load(f)
            logger.info(f"Loaded model metadata from {meta_path}")
        except Exception as e:
            logger.warning(f"Failed to load metadata: {e}")

    # Use metadata to override defaults
    if feature_type is None and "feature_type" in meta_cfg:
        feature_type = meta_cfg["feature_type"]
    
    # If n_mels is default, try to use metadata
    if n_mels == DEFAULT_N_MELS and "n_mels" in meta_cfg:
        n_mels = meta_cfg["n_mels"]

    emb_dim = meta_cfg.get("emb_dim", EMBEDDING_DIM)

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
    model = LightECAPA(feat_dim=feat_dim, emb_dim=emb_dim, n_speakers=None).to(device)
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
        
        # Initialize VectorStore
        try:
            self.vector_store = VectorStore()
            logger.info("VoiceService: VectorStore connected.")
        except Exception as e:
            logger.error(f"VoiceService: Failed to connect VectorStore: {e}")
            self.vector_store = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls, model_path: str = None, device: str = None):
        cls._instance = cls(model_path=model_path, device=device)
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

            # Use VectorStore if available
            if self.vector_store:
                try:
                    self.vector_store.add(
                        user_id=user_id,
                        embedding=user_template,
                        metadata={
                            "wav_count": len(wav_paths),
                            "updated_at": str(os.path.getmtime(wav_paths[0])),
                        },
                    )
                except Exception as e:
                    logger.error(f"VectorStore add failed for {user_id}: {e}")

            # Always keep legacy templates in sync for preview/backup
            templates = load_templates(TEMPLATE_PATH)
            templates[user_id] = user_template
            save_templates(templates, TEMPLATE_PATH)
            
            logger.info(f"Enrolled user {user_id} with {len(wav_paths)} samples.")
            return {"status": "success", "user_id": user_id, "wav_count": len(wav_paths)}
            
        except Exception as e:
            logger.error(f"Enrollment failed for {user_id}: {e}")
            return {"status": "error", "error": str(e)}

    def get_feature(self, user_id: str) -> Optional[np.ndarray]:
        """Retrieve voiceprint feature for a user."""
        
        # 1. Prefer VectorStore (Primary Source of Truth)
        if self.vector_store:
            try:
                emb = self.vector_store.get(user_id)
                if emb is not None:
                    logger.info(f"Retrieved feature for {user_id} from VectorStore (ChromaDB)")
                    return emb
            except Exception as e:
                logger.warning(f"VectorStore retrieval failed for {user_id}: {e}")

        # 2. Fallback to legacy templates (Backup/Migration)
        templates = load_templates()
        emb = templates.get(user_id)
        if emb is not None:
            logger.info(f"Retrieved feature for {user_id} from Legacy Templates (.npy)")
            return emb

        return None

    def delete_feature(self, user_id: str) -> bool:
        """Delete voiceprint feature for a user."""
        deleted = False
        # 1. Delete from VectorStore
        if self.vector_store:
            try:
                self.vector_store.delete(user_id)
                deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete from VectorStore: {e}")

        # 2. Delete from .npy templates (Legacy)
        templates = load_templates()
        if user_id in templates:
            del templates[user_id]
            try:
                save_templates(templates)
                deleted = True
            except Exception as e:
                logger.error(f"Failed to save templates after deletion: {e}")
        
        return deleted

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

            best_spk, best_score = None, -1.0

            # Use VectorStore if available
            if self.vector_store and self.vector_store.count() > 0:
                matches = self.vector_store.search(emb, top_k=1)
                if matches:
                    best_spk, best_score = matches[0]
            else:
                # Fallback to legacy
                templates = load_templates(TEMPLATE_PATH)
                if not templates:
                    return {"status": "reject", "score": 0.0, "speaker": None, "message": "No enrolled users"}

                for spk, tmpl in templates.items():
                    if isinstance(tmpl, np.ndarray) and tmpl.ndim == 1:
                        s = cosine_score(emb, tmpl)
                    elif isinstance(tmpl, (list, np.ndarray)):
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
                "predicted_user": best_spk, # Compatible with legacy API
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
