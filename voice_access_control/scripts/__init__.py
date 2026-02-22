import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
FEATURES_DIR = DATA_DIR / "features"
ENROLL_DIR = DATA_DIR / "enroll"
RECORDINGS_DIR = DATA_DIR / "recordings"
VOICEPRINTS_DIR = DATA_DIR / "voiceprints"
MODELS_DIR = PROJECT_ROOT / "checkpoints"
REPORTS_DIR = PROJECT_ROOT / "reports"

def ensure_project_root():
    root = os.fspath(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return root
