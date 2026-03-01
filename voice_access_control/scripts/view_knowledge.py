import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice_engine.services.knowledge_service import KnowledgeService

def view_knowledge():
    print("Connecting to Knowledge Base (ChromaDB)...", flush=True)
    try:
        ks = KnowledgeService.get_instance()
        if ks.vector_store is None:
            print("Error: Vector store not initialized.", flush=True)
            return

        # Get the underlying collection
        collection = ks.vector_store._collection
        
        # Get all data
        data = collection.get()
        
        if not data['ids']:
            print("Knowledge Base is EMPTY.", flush=True)
            return

        print(f"\nFound {len(data['ids'])} documents:\n", flush=True)
        
        # Create a DataFrame for better display
        df = pd.DataFrame({
            'ID': data['ids'],
            'Content': data['documents'],
            'Metadata': [str(m) for m in data['metadatas']]
        })
        
        # Adjust display options
        pd.set_option('display.max_colwidth', 80)
        pd.set_option('display.max_rows', None)
        pd.set_option('display.width', 1000)
        
        print(df.to_string(index=False), flush=True)
        
        persist_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "chroma_knowledge")))
        print(f"\n[Storage Info]", flush=True)
        print(f"Type: Local File-based Vector Database (SQLite + Parquet)", flush=True)
        print(f"Path: {persist_dir}", flush=True)
        print(f"Note: This is NOT stored in MySQL. It is a specialized vector store.", flush=True)

    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    view_knowledge()
