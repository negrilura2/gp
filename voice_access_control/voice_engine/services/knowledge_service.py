import os
import logging
import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from ..config import (
    CHROMA_KNOWLEDGE_DIR,
    RAG_EMBEDDING_MODEL,
    KNOWLEDGE_COLLECTION_NAME,
    VOICE_ENGINE_DEVICE
)
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

class KnowledgeService:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """
        Initialize the RAG Knowledge Service.
        Uses ChromaDB for vector storage and HuggingFace for embeddings.
        """
        try:
            # 1. Initialize Embeddings
            # 使用支持多语言（含中文）的轻量级模型
            # 如果下载慢，可以手动下载模型并指定本地路径
            model_name = os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            model_kwargs = {'device': 'cpu'} # 默认用CPU，避免显存冲突
            encode_kwargs = {'normalize_embeddings': True}
            
            logger.info(f"Loading embedding model: {model_name}...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs
            )

            # 2. Initialize Vector Store (ChromaDB)
            # 使用持久化存储，路径与声纹数据库分开，或者共用同一个目录的不同 Collection
            persist_directory = os.path.join(DATA_DIR, "chroma_knowledge")
            
            self.vector_store = Chroma(
                collection_name="local_knowledge_base",
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            )
            
            logger.info(f"KnowledgeService initialized. Persist dir: {persist_directory}")
            
            # 3. Check and initialize default data if empty
            # Use try-except block to handle potential issues with accessing the collection
            try:
                # Some versions of Chroma/LangChain might behave differently if collection is empty or not fully init
                count = self.vector_store._collection.count()
                logger.info(f"Current knowledge base document count: {count}")
                
                if count == 0:
                    self._init_default_knowledge()
                else:
                    # Optional: Force check if critical data exists
                    # If "物业" search returns nothing, re-add defaults (handling possible data corruption or old schema)
                    try:
                        test_res = self.vector_store.similarity_search("物业", k=1)
                        if not test_res:
                             logger.warning("Knowledge base has data but '物业' not found. Re-initializing defaults...")
                             self._init_default_knowledge()
                    except Exception as e:
                        logger.warning(f"Self-check failed: {e}")
            except Exception as e:
                logger.error(f"Error checking/initializing vector store data: {e}")
                # Fallback: try to init anyway if check failed
                self._init_default_knowledge()

        except Exception as e:
            logger.error(f"Failed to initialize KnowledgeService: {e}")
            self.vector_store = None

    def _init_default_knowledge(self):
        """Initialize with some example data"""
        logger.info("Initializing default knowledge base...")
        texts = [
            "小区的物业电话是 010-12345678。",
            "家里的WiFi名称是 'MyHome_5G'，密码是 'hello123456'。",
            "如果发生火灾，请立即拨打119，并从北面的安全出口撤离。",
            "快递一般会放在门口的白色柜子里。",
            "垃圾分类要求：厨余垃圾扔绿桶，其他垃圾扔黑桶。",
            "门禁系统的管理员是郭先生，联系电话 13800138000。"
        ]
        metadatas = [{"source": "default_init", "category": "info"} for _ in texts]
        self.add_texts(texts, metadatas)

    def add_texts(self, texts: list[str], metadatas: list[dict] = None):
        """Add new texts to the knowledge base"""
        if self.vector_store is None:
            logger.warning("Vector store not initialized. Cannot add texts.")
            return
        
        if metadatas is None:
            metadatas = [{"source": "user_added"} for _ in texts]
        
        try:
            self.vector_store.add_texts(texts=texts, metadatas=metadatas)
            logger.info(f"Added {len(texts)} documents to knowledge base.")
        except Exception as e:
            logger.error(f"Failed to add texts to vector store: {e}")

    def search(self, query: str, k: int = 3) -> list[Document]:
        """Search for relevant documents"""
        if not self.vector_store:
            return []
        
        logger.info(f"Searching knowledge base for: {query}")
        # Use similarity_search_with_score to debug relevance
        # Note: Chroma distance is Euclidean/Cosine distance (lower is better usually, depends on space)
        # LangChain defaults to cosine similarity (higher is better) for some stores, but Chroma wrapper returns documents
        try:
            results = self.vector_store.similarity_search(query, k=k)
            if not results:
                logger.warning(f"No results found for query: {query}")
            else:
                logger.info(f"Found {len(results)} results. Top: {results[0].page_content[:20]}...")
            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_knowledge_context(self, query: str) -> str:
        """Get formatted context string for LLM"""
        docs = self.search(query)
        if not docs:
            return ""
        
        context = "\n".join([f"- {doc.page_content}" for doc in docs])
        return f"\n【本地知识库参考信息】:\n{context}\n"
