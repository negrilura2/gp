"""
Script to migrate legacy .npy voiceprints to ChromaDB Vector Store.
"""
import os
import sys
import logging
import numpy as np
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from voice_engine.vector_store import VectorStore
from voice_engine.config import TEMPLATE_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_to_chroma")

def migrate():
    logger.info("Starting migration from .npy to ChromaDB...")
    
    # 1. Load legacy .npy templates
    if not os.path.exists(TEMPLATE_PATH):
        logger.warning(f"No legacy template file found at {TEMPLATE_PATH}. Nothing to migrate.")
        return

    try:
        templates = np.load(TEMPLATE_PATH, allow_pickle=True).item()
    except Exception as e:
        logger.error(f"Failed to load .npy file: {e}")
        return

    if not templates:
        logger.info("Legacy template file is empty.")
        return

    logger.info(f"Found {len(templates)} users in legacy templates.")

    # 2. Initialize VectorStore
    try:
        vector_store = VectorStore()
    except Exception as e:
        logger.error(f"Failed to initialize VectorStore: {e}")
        return

    # 3. Migrate each user
    success_count = 0
    for user_id, embedding in templates.items():
        try:
            # Handle different embedding formats (single vector vs list of vectors)
            # Legacy code might store list of embeddings for multi-enrollment
            # We take the mean if it's a list/matrix, or just use it if it's a vector
            
            final_emb = None
            if isinstance(embedding, (list, tuple)):
                embedding = np.array(embedding)
            
            if isinstance(embedding, np.ndarray):
                if embedding.ndim == 1:
                    final_emb = embedding
                elif embedding.ndim == 2:
                    # Average multiple embeddings
                    final_emb = np.mean(embedding, axis=0)
                else:
                    logger.warning(f"Skipping user {user_id}: embedding has unexpected shape {embedding.shape}")
                    continue
            else:
                logger.warning(f"Skipping user {user_id}: unknown embedding type {type(embedding)}")
                continue

            # Add to Chroma
            vector_store.add(
                user_id=user_id, 
                embedding=final_emb,
                metadata={"source": "migration_from_npy", "original_count": 1}
            )
            success_count += 1
            logger.info(f"Migrated user: {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to migrate user {user_id}: {e}")

    logger.info(f"Migration complete. Successfully migrated {success_count}/{len(templates)} users.")
    logger.info(f"Total count in ChromaDB: {vector_store.count()}")

if __name__ == "__main__":
    migrate()
