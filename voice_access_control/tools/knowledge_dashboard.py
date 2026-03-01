import streamlit as st
import pandas as pd
import os
import sys

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from voice_engine.services.knowledge_service import KnowledgeService
import chromadb
from chromadb.config import Settings
import numpy as np

st.set_page_config(page_title="Vector Database Manager", layout="wide", page_icon="📚")

st.title("📚 Local Vector Database Manager")
st.markdown("Use this dashboard to inspect your local vector databases (ChromaDB).")

# --- Sidebar: Database Selection ---
db_option = st.sidebar.radio(
    "Select Database",
    ("Knowledge Base (RAG)", "Voiceprints (声纹库)")
)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
knowledge_path = os.path.join(project_root, "data", "chroma_knowledge")
voiceprint_path = os.path.join(project_root, "data", "chroma_db")

# Global variables for the selected DB
active_collection = None
is_voiceprint = False

# --- Database Connection Logic ---
try:
    if db_option == "Knowledge Base (RAG)":
        st.sidebar.success(f"📂 Path: {knowledge_path}")
        ks = KnowledgeService.get_instance()
        if ks.vector_store:
            active_collection = ks.vector_store._collection
        else:
            st.error("❌ Knowledge Service Vector Store not initialized!")
    
    else: # Voiceprints
        st.sidebar.warning(f"📂 Path: {voiceprint_path}")
        is_voiceprint = True
        # Direct ChromaDB connection for voiceprints (since it doesn't use LangChain wrapper usually)
        if os.path.exists(voiceprint_path):
            client = chromadb.PersistentClient(path=voiceprint_path)
            # Try to get the default collection or list all
            cols = client.list_collections()
            if not cols:
                 # Attempt to get default if list is empty but folder exists
                 active_collection = client.get_or_create_collection("voice_vectors")
            else:
                 # Let user choose if multiple, or pick first
                 col_names = [c.name for c in cols]
                 selected_col = st.sidebar.selectbox("Select Collection", col_names)
                 active_collection = client.get_collection(selected_col)
        else:
            st.error(f"❌ Voiceprint database not found at {voiceprint_path}")

except Exception as e:
    st.error(f"❌ Connection Error: {e}")
    st.stop()

if not active_collection:
    st.warning("⚠️ No active collection found or connected.")
    st.stop()

# --- Main Content ---

# Tabs
tab1, tab2, tab3 = st.tabs(["🔍 Inspect & Search", "➕ Add Data", "📊 Stats"])

with tab1:
    st.header(f"Inspect: {db_option}")
    
    if is_voiceprint:
        st.info("ℹ️ Voiceprints are dense vectors. Semantic text search is NOT available here. You can browse users.")
        
        if st.button("Load All Voiceprints"):
            # Explicitly request embeddings, otherwise Chroma might only return metadata/ids
            data = active_collection.get(include=["metadatas", "embeddings"])
            if not data['ids']:
                st.info("Voiceprint database is empty.")
                st.session_state['voiceprint_data'] = None
            else:
                # Format for display
                display_data = []
                for i, uid in enumerate(data['ids']):
                    meta = data['metadatas'][i] if data['metadatas'] else {}
                    
                    # Safe embedding access
                    emb_list = data.get('embeddings')
                    emb = emb_list[i] if emb_list is not None and i < len(emb_list) else None
                    
                    if emb is not None:
                        emb_len = len(emb)
                        emb_preview = f"[{emb[0]:.4f}, {emb[1]:.4f}, ... {emb[-1]:.4f}] ({emb_len}-dim)"
                    else:
                        emb_preview = "N/A"

                    display_data.append({
                        "User ID": uid,
                        "Metadata": meta,
                        "Embedding (Preview)": emb_preview,
                        "_emb": emb # Hidden field for visualization
                    })
                
                df = pd.DataFrame(display_data)
                st.session_state['voiceprint_data'] = df
        
        # Check if data exists in session state
        if 'voiceprint_data' in st.session_state and st.session_state['voiceprint_data'] is not None:
            df = st.session_state['voiceprint_data']
            
            # Show main table
            st.dataframe(df.drop(columns=["_emb"]), width=1200) # Replaced use_container_width with width
            
            st.divider()
            st.subheader("📊 Vector Visualization")
            
            # Let user select a user to visualize
            selected_user = st.selectbox("Select User to Visualize:", df["User ID"].unique())
            
            if selected_user:
                user_row = df[df["User ID"] == selected_user].iloc[0]
                vec = user_row["_emb"]
                
                if vec is not None:
                    # 1. Line Chart
                    st.write(f"**Vector Dimensions (Line Chart):** {selected_user}")
                    chart_data = pd.DataFrame(vec, columns=["Value"])
                    st.line_chart(chart_data)
                    
                    # 2. Heatmap (reshaped)
                    # Try to find a suitable rectangle shape for the heatmap
                    vec_len = len(vec)
                    st.write(f"**Vector Heatmap ({vec_len}-dim):** {selected_user}")
                    
                    try:
                        # Auto-calculate dimensions
                        # Find factors close to square root
                        sqrt_len = int(np.sqrt(vec_len))
                        cols = sqrt_len
                        while vec_len % cols != 0:
                            cols -= 1
                        rows = vec_len // cols
                        
                        matrix = np.array(vec).reshape(rows, cols)
                        try:
                            import plotly.express as px
                            fig = px.imshow(matrix, labels=dict(x="Dim X", y="Dim Y", color="Value"),
                                            title=f"{vec_len}-dim Feature Map ({rows}x{cols})")
                            st.plotly_chart(fig)
                        except ImportError:
                            # Fallback to matplotlib if plotly is not installed
                            import matplotlib.pyplot as plt
                            fig, ax = plt.subplots(figsize=(6, 4))
                            im = ax.imshow(matrix, cmap='viridis')
                            plt.colorbar(im)
                            ax.set_title(f"{vec_len}-dim Feature Map ({rows}x{cols})")
                            st.pyplot(fig)
                            st.info("ℹ️ Using Matplotlib fallback (Plotly not found). For interactive charts: `pip install plotly`")
                    except Exception as e:
                        st.info(f"Could not render heatmap: {e}")
                else:
                    st.warning("No embedding data available for this user.")
                
    else:
        # Knowledge Base Logic (Text Search)
        query = st.text_input("Enter a query to test semantic search:", placeholder="e.g., 物业电话是多少？")
        col1, col2 = st.columns([1, 1])
        with col1:
            top_k = st.slider("Top K Results", min_value=1, max_value=10, value=3)
        
        if query:
             # Reuse KnowledgeService for search if available
             if db_option == "Knowledge Base (RAG)":
                 # ... existing search logic ...
                 with st.spinner("Searching..."):
                    try:
                        # We use the raw collection for query to be consistent across tabs, 
                        # but for text search we need embeddings. 
                        # KnowledgeService has the embedding function configured.
                        results = ks.search(query, k=top_k)
                        if not results:
                            st.warning("No relevant documents found.")
                        else:
                            st.success(f"Found {len(results)} relevant documents.")
                            for i, doc in enumerate(results):
                                with st.expander(f"Result #{i+1}", expanded=True):
                                    st.markdown(f"**Content:**\n> {doc.page_content}")
                                    st.json(doc.metadata)
                    except Exception as e:
                        st.error(f"Search failed: {e}")

        st.divider()
        if st.button("Load All Documents"):
             data = active_collection.get()
             if not data['ids']:
                 st.info("Database is empty.")
             else:
                 df = pd.DataFrame({
                     'ID': data['ids'],
                     'Content': data['documents'],
                     'Metadata': [str(m) for m in data['metadatas']]
                 })
                 st.dataframe(df, width=1200)

with tab2:
    if is_voiceprint:
        st.warning("⚠️ Manually adding voiceprints via this dashboard is not supported. Please use the Voice Engine API.")
    else:
        st.header("Add New Knowledge")
        with st.form("add_knowledge_form"):
            new_text = st.text_area("Content", height=150)
            category = st.selectbox("Category", ["info", "rule", "contact", "manual", "other"])
            submitted = st.form_submit_button("Add")
            
            if submitted and new_text:
                try:
                    metadata = [{"source": "dashboard", "category": category}]
                    ks.add_texts([new_text], metadata)
                    st.success("✅ Added!")
                except Exception as e:
                    st.error(f"Failed: {e}")

with tab3:
    st.header("Database Statistics")
    try:
        count = active_collection.count()
        st.metric("Total Entries", count)
        
        current_path = voiceprint_path if is_voiceprint else knowledge_path
        st.code(f"Storage Path: {current_path}", language="bash")
        
        if is_voiceprint:
             st.markdown("### Voiceprint DB Details\n- **Vectors**: Audio Embeddings (192-dim)\n- **Metadata**: User info, timestamps")
        else:
             st.markdown("### Knowledge DB Details\n- **Vectors**: Text Embeddings\n- **Metadata**: Source, Category")
            
    except Exception as e:
        st.error(f"Failed to load stats: {e}")
