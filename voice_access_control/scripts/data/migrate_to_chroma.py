import os
import sys
import numpy as np
import logging

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.vector_store import VectorStore
from voice_engine.config import TEMPLATE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate")

def main():
    if not os.path.exists(TEMPLATE_PATH):
        logger.error(f"Template file not found: {TEMPLATE_PATH}")
        return

    logger.info(f"Loading templates from {TEMPLATE_PATH}...")
    try:
        templates = np.load(TEMPLATE_PATH, allow_pickle=True).item()
    except Exception as e:
        logger.error(f"Failed to load .npy file: {e}")
        return

    logger.info(f"Found {len(templates)} users in .npy file.")

    logger.info("Initializing ChromaDB VectorStore...")
    try:
        vs = VectorStore()
    except Exception as e:
        logger.error(f"Failed to initialize VectorStore: {e}")
        return
    
    success_count = 0
    fail_count = 0

    for user_id, embedding in templates.items():
        try:
            # Ensure embedding is 1D array
            if isinstance(embedding, list):
                embedding = np.array(embedding)
            
            if embedding.ndim != 1:
                logger.warning(f"Skipping {user_id}: embedding shape {embedding.shape} is not 1D")
                fail_count += 1
                continue

            vs.add(
                user_id=user_id,
                embedding=embedding,
                metadata={"source": "migration", "legacy": True, "username": user_id}
            )
            success_count += 1
            
            if success_count % 10 == 0:
                logger.info(f"Migrated {success_count} users...")
                
        except Exception as e:
            logger.error(f"Failed to migrate {user_id}: {e}")
            fail_count += 1

    logger.info(f"Migration completed. Success: {success_count}, Failed: {fail_count}")
    logger.info(f"Total in ChromaDB: {vs.count()}")

if __name__ == "__main__":
    main()
