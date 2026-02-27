import os
import sys
import numpy as np
import logging
import argparse

# Add project root to path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from voice_engine.vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("debug_chroma")

def main():
    parser = argparse.ArgumentParser(description="Debug ChromaDB Data")
    parser.add_argument("--user", type=str, help="Specific username to query")
    args = parser.parse_args()

    print("-" * 50)
    print("🚀 ChromaDB Data Debugger")
    print("-" * 50)

    try:
        vs = VectorStore()
        count = vs.count()
        print(f"✅ Connection Successful")
        print(f"📊 Total Documents: {count}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        return

    if count == 0:
        print("\n⚠️  WARNING: Collection is EMPTY!")
        return

    # 1. List first 5 IDs
    print("\n🔍 1. Listing first 5 IDs:")
    try:
        # peek() returns dict with 'ids', 'embeddings', etc.
        peek_res = vs._collection.peek(limit=5)
        ids = peek_res.get('ids', [])
        for i, uid in enumerate(ids):
            print(f"   [{i}] {uid}")
    except Exception as e:
        print(f"   ❌ Failed to peek collection: {e}")

    # 2. Check dimension of a random sample
    print("\n📏 2. Dimension Check (First Sample):")
    if ids:
        sample_id = ids[0]
        try:
            emb = vs.get(sample_id)
            if emb is not None:
                print(f"   ID: {sample_id}")
                print(f"   Type: {type(emb)}")
                print(f"   Shape: {emb.shape}")
                print(f"   Dtype: {emb.dtype}")
                print(f"   First 5 values: {emb[:5]}")
            else:
                print(f"   ❌ vs.get({sample_id}) returned None (Unexpected)")
        except Exception as e:
            print(f"   ❌ Error checking dimension: {e}")

    # 3. ID Match Test
    if args.user:
        print(f"\n🎯 3. ID Match Test for '{args.user}':")
        try:
            # Check using get()
            emb = vs.get(args.user)
            if emb is not None:
                print(f"   ✅ Found!")
                print(f"   Shape: {emb.shape}")
            else:
                print(f"   ❌ Not Found via vs.get()")
                
                # Debug: Try to find if it exists in metadata username
                print("   🕵️  Searching in metadata...")
                res = vs._collection.get(where={"username": args.user})
                if res['ids']:
                    print(f"   ✅ Found via metadata['username']! IDs: {res['ids']}")
                    print("   ⚠️  Mismatch: stored ID is different from username?")
                else:
                    print("   ❌ Not found in metadata either.")
        except Exception as e:
            print(f"   ❌ Error during ID match test: {e}")
    else:
        print("\nℹ️  Tip: Run with --user <username> to test specific user lookup.")

    print("-" * 50)

if __name__ == "__main__":
    main()
