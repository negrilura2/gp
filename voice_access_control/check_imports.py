
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

print("Checking imports...")
try:
    from voice_engine import metrics
    print("✅ voice_engine.metrics imported")
except ImportError as e:
    print(f"❌ voice_engine.metrics failed: {e}")

try:
    from voice_engine import augmentation
    print("✅ voice_engine.augmentation imported")
except ImportError as e:
    print(f"❌ voice_engine.augmentation failed: {e}")

try:
    from voice_engine import evaluation
    print("✅ voice_engine.evaluation imported")
except ImportError as e:
    print(f"❌ voice_engine.evaluation failed: {e}")

try:
    from voice_engine.service import VoiceService
    print("✅ voice_engine.service imported")
except ImportError as e:
    print(f"❌ voice_engine.service failed: {e}")

print("Done.")
