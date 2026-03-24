"""
Vector Store Interface using ChromaDB.
Replaces legacy .npy file traversal with vector database search.
"""
import os
import logging
import numpy as np
import chromadb
from typing import List, Tuple, Dict, Optional, Any
from ..config import CHROMA_DB_DIR

# 简单日志配置，避免导入错误
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_engine.vector_store")

class VectorStore:
    def __init__(self, persist_path: str = None, collection_name: str = "voiceprints"):
        # Default path relative to project root if not specified
        if not persist_path:
            persist_path = CHROMA_DB_DIR
            
        self.persist_path = persist_path
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._init_db()

    def _init_db(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Ensure directory exists
            os.makedirs(self.persist_path, exist_ok=True)
            
            # Initialize persistent client
            self._client = chromadb.PersistentClient(path=self.persist_path)
            
            # Get or create collection
            # We use cosine distance space for embeddings
            # ChromaDB default distance function is L2, so we specify cosine
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"VectorStore initialized at {self.persist_path}, collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    def add(self, user_id: str, embedding: np.ndarray, metadata: Dict[str, Any] = None):
        """
        Add or update a user's voiceprint embedding.
        If user_id exists, it will be updated (upsert).
        
        Args:
            user_id: Unique user identifier
            embedding: 1D numpy array of embedding
            metadata: Optional dictionary of metadata (e.g. timestamp, wav_count)
        """
        if embedding.ndim != 1:
            raise ValueError(f"Embedding must be 1D array, got shape {embedding.shape}")
        
        embedding = embedding / (np.linalg.norm(embedding) + 1e-9)

        meta = dict(metadata) if metadata else {}
        if "user_id" not in meta:
            meta["user_id"] = user_id
        if "username" not in meta and "username" in meta:
            pass
        elif "username" not in meta:
            meta["username"] = user_id

        try:
            self._collection.upsert(
                ids=[user_id],
                embeddings=[embedding.tolist()],
                metadatas=[meta]
            )
            logger.info(f"Upserted voiceprint for user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to add voiceprint for {user_id}: {e}")
            raise

    def search(self, query_embedding: np.ndarray, top_k: int = 1) -> List[Tuple[str, float]]:
        """
        Search for most similar voiceprints.
        
        Args:
            query_embedding: 1D numpy array
            top_k: Number of results to return
            
        Returns:
            List of (user_id, score) tuples. 
            Score is converted to cosine similarity (0-1 range, higher is better).
            Chroma returns cosine distance (lower is better), so we convert: sim = 1 - dist
        """
        if query_embedding.ndim != 1:
            raise ValueError(f"Query embedding must be 1D array, got shape {query_embedding.shape}")
            
        # Normalize query
        query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-9)
        
        try:
            results = self._collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                include=["metadatas", "distances"]
            )
            
            # Parse results
            # Chroma structure: {'ids': [['alice']], 'distances': [[0.15]], ...}
            if not results['ids'] or not results['ids'][0]:
                return []
            
            # Extract first batch (since we only query one vector)
            ids = results['ids'][0]
            distances = results['distances'][0]
            
            matches = []
            for uid, dist in zip(ids, distances):
                # Convert cosine distance to cosine similarity
                # Chroma cosine distance is 1 - cosine_similarity
                # So similarity = 1 - distance
                sim = 1.0 - dist
                matches.append((uid, float(sim)))
            
            return matches
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def delete(self, user_id: str):
        """Delete a user's voiceprint"""
        try:
            self._collection.delete(ids=[user_id])
            logger.info(f"Deleted voiceprint for user: {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            raise

    def count(self) -> int:
        """Return total number of embeddings"""
        return self._collection.count()

    def get(self, user_id: str) -> Optional[np.ndarray]:
        try:
            res = self._collection.get(ids=[user_id], include=["embeddings"])
        
        # 1. 基础结构校验
            if res is None or 'embeddings' not in res or res['embeddings'] is None:
                return None
            
            embedding_list = res['embeddings']
            if len(embedding_list) == 0:
                return None

            first_embedding = embedding_list[0]
        
        # 2. 【核心修复点】不要使用 if not first_embedding
        # 使用 len() 或者 is None 来判断
            if first_embedding is None or len(first_embedding) == 0:
                return None
            
        # 强制转换为 float64，并确保它是扁平的一维数组
            return np.array(first_embedding, dtype=np.float64).flatten()
        
        except Exception as e:
        # 这里能帮你看到具体的报错
            logger.error(f"Error retrieving embedding for {user_id}: {str(e)}")
            return None

    def clear(self):
        """Clear all data (Use with caution!)"""
        try:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.warning("VectorStore cleared.")
        except Exception as e:
            logger.error(f"Failed to clear VectorStore: {e}")
