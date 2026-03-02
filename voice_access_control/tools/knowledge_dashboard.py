import streamlit as st
import pandas as pd
import os
import sys

# =============================================================================
# 使用说明 (Usage Guide)
# =============================================================================
# 该脚本是一个用于可视化和管理本地向量数据库 (ChromaDB) 的 Streamlit 仪表盘。
#
# 功能：
# 1. 查看知识库 (Knowledge Base) 中的文本数据和元数据。
# 2. 测试语义搜索 (RAG) 功能。
# 3. 查看声纹库 (Voiceprints) 中的用户 ID 和声纹向量。
# 4. 可视化声纹向量 (折线图、热力图)。
# 5. 添加新的知识条目 (仅限知识库)。
#
# 运行方法：
# 在终端中运行以下命令：
# streamlit run tools/knowledge_dashboard.py
# =============================================================================

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from voice_engine.services.knowledge_service import KnowledgeService
import chromadb
from chromadb.config import Settings
import numpy as np

st.set_page_config(page_title="向量数据库管理器 (Vector Database Manager)", layout="wide", page_icon="📚")

st.title("📚 本地向量数据库管理器")
st.markdown("使用此仪表盘检查您的本地向量数据库 (ChromaDB)。")

# --- Sidebar: Database Selection ---
# 侧边栏：选择要检查的数据库类型
db_option = st.sidebar.radio(
    "选择数据库 (Select Database)",
    ("知识库 (RAG - Knowledge Base)", "声纹库 (Voiceprints)")
)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
knowledge_path = os.path.join(project_root, "data", "chroma_knowledge")
voiceprint_path = os.path.join(project_root, "data", "chroma_db")

# Global variables for the selected DB
active_collection = None
is_voiceprint = False

# --- Database Connection Logic ---
try:
    if db_option == "知识库 (RAG - Knowledge Base)":
        st.sidebar.success(f"📂 路径: {knowledge_path}")
        # 初始化知识库服务
        ks = KnowledgeService.get_instance()
        if ks.vector_store:
            active_collection = ks.vector_store._collection
        else:
            st.error("❌ 知识库服务 (Knowledge Service) 未初始化！")
    
    else: # Voiceprints
        st.sidebar.warning(f"📂 路径: {voiceprint_path}")
        is_voiceprint = True
        # 声纹库通常不通过 LangChain 封装，而是直接使用 ChromaDB 客户端连接
        if os.path.exists(voiceprint_path):
            client = chromadb.PersistentClient(path=voiceprint_path)
            # 获取所有集合
            cols = client.list_collections()
            if not cols:
                 # 如果没有集合但文件夹存在，尝试获取默认集合
                 active_collection = client.get_or_create_collection("voice_vectors")
            else:
                 # 如果有多个集合，让用户选择
                 col_names = [c.name for c in cols]
                 selected_col = st.sidebar.selectbox("选择集合 (Collection)", col_names)
                 active_collection = client.get_collection(selected_col)
        else:
            st.error(f"❌ 未找到声纹数据库，路径: {voiceprint_path}")

except Exception as e:
    st.error(f"❌ 连接错误: {e}")
    st.stop()

if not active_collection:
    st.warning("⚠️ 未找到或未连接到活动的集合 (Collection)。")
    st.stop()

# --- Main Content ---

# Tabs: 分别为“检查与搜索”、“添加数据”、“统计信息”
tab1, tab2, tab3 = st.tabs(["🔍 检查与搜索 (Inspect & Search)", "➕ 添加数据 (Add Data)", "📊 统计信息 (Stats)"])

with tab1:
    st.header(f"检查: {db_option}")
    
    if is_voiceprint:
        st.info("ℹ️ 声纹库存储的是稠密向量。此处不支持语义文本搜索，您可以浏览用户列表和向量可视化。")
        
        if st.button("加载所有声纹 (Load All Voiceprints)"):
            # 显式请求 embeddings，否则 Chroma 可能只返回 metadata/ids
            data = active_collection.get(include=["metadatas", "embeddings"])
            if not data['ids']:
                st.info("声纹数据库为空。")
                st.session_state['voiceprint_data'] = None
            else:
                # 格式化显示数据
                display_data = []
                for i, uid in enumerate(data['ids']):
                    meta = data['metadatas'][i] if data['metadatas'] else {}
                    
                    # 安全获取 embedding
                    emb_list = data.get('embeddings')
                    emb = emb_list[i] if emb_list is not None and i < len(emb_list) else None
                    
                    if emb is not None:
                        emb_len = len(emb)
                        emb_preview = f"[{emb[0]:.4f}, {emb[1]:.4f}, ... {emb[-1]:.4f}] ({emb_len}维)"
                    else:
                        emb_preview = "N/A"

                    display_data.append({
                        "用户 ID (User ID)": uid,
                        "元数据 (Metadata)": meta,
                        "向量预览 (Embedding Preview)": emb_preview,
                        "_emb": emb # 隐藏字段，用于后续可视化
                    })
                
                df = pd.DataFrame(display_data)
                st.session_state['voiceprint_data'] = df
        
        # 检查 session_state 中是否有数据
        if 'voiceprint_data' in st.session_state and st.session_state['voiceprint_data'] is not None:
            df = st.session_state['voiceprint_data']
            
            # 显示主表格
            st.dataframe(df.drop(columns=["_emb"]), width=1200)
            
            st.divider()
            st.subheader("📊 向量可视化 (Vector Visualization)")
            
            # 让用户选择一个用户进行可视化
            selected_user = st.selectbox("选择要可视化的用户:", df["用户 ID (User ID)"].unique())
            
            if selected_user:
                user_row = df[df["用户 ID (User ID)"] == selected_user].iloc[0]
                vec = user_row["_emb"]
                
                if vec is not None:
                    # 1. 折线图 (Line Chart)
                    st.write(f"**向量维度分布 (折线图):** {selected_user}")
                    chart_data = pd.DataFrame(vec, columns=["Value"])
                    st.line_chart(chart_data)
                    
                    # 2. 热力图 (Heatmap)
                    vec_len = len(vec)
                    st.write(f"**向量热力图 ({vec_len}维):** {selected_user}")
                    
                    try:
                        # 自动计算矩阵维度，使其接近正方形
                        sqrt_len = int(np.sqrt(vec_len))
                        cols = sqrt_len
                        while vec_len % cols != 0:
                            cols -= 1
                        rows = vec_len // cols
                        
                        matrix = np.array(vec).reshape(rows, cols)
                        try:
                            import plotly.express as px
                            fig = px.imshow(matrix, labels=dict(x="Dim X", y="Dim Y", color="Value"),
                                            title=f"{vec_len}维 特征图 ({rows}x{cols})")
                            st.plotly_chart(fig)
                        except ImportError:
                            # 如果没有安装 plotly，回退到 matplotlib
                            import matplotlib.pyplot as plt
                            fig, ax = plt.subplots(figsize=(6, 4))
                            im = ax.imshow(matrix, cmap='viridis')
                            plt.colorbar(im)
                            ax.set_title(f"{vec_len}维 特征图 ({rows}x{cols})")
                            st.pyplot(fig)
                            st.info("ℹ️ 使用 Matplotlib 回退显示 (未找到 Plotly)。如需交互式图表请安装: `pip install plotly`")
                    except Exception as e:
                        st.info(f"无法渲染热力图: {e}")
                else:
                    st.warning("该用户没有向量数据。")
                
    else:
        # 知识库逻辑 (语义搜索)
        query = st.text_input("输入查询以测试语义搜索:", placeholder="例如：物业电话是多少？")
        col1, col2 = st.columns([1, 1])
        with col1:
            top_k = st.slider("返回结果数量 (Top K)", min_value=1, max_value=10, value=3)
        
        if query:
             # 复用 KnowledgeService 进行搜索
             if db_option == "知识库 (RAG - Knowledge Base)":
                 with st.spinner("正在搜索..."):
                    try:
                        results = ks.search(query, k=top_k)
                        if not results:
                            st.warning("未找到相关文档。")
                        else:
                            st.success(f"找到 {len(results)} 个相关文档。")
                            for i, doc in enumerate(results):
                                with st.expander(f"结果 #{i+1}", expanded=True):
                                    st.markdown(f"**内容:**\n> {doc.page_content}")
                                    st.json(doc.metadata)
                    except Exception as e:
                        st.error(f"搜索失败: {e}")

        st.divider()
        if st.button("加载所有文档 (Load All Documents)"):
             data = active_collection.get()
             if not data['ids']:
                 st.info("数据库为空。")
             else:
                 df = pd.DataFrame({
                     'ID': data['ids'],
                     '内容 (Content)': data['documents'],
                     '元数据 (Metadata)': [str(m) for m in data['metadatas']]
                 })
                 st.dataframe(df, width=1200)

with tab2:
    if is_voiceprint:
        st.warning("⚠️ 不支持通过此仪表盘手动添加声纹。请使用 Voice Engine API 或录音脚本。")
    else:
        st.header("添加新知识 (Add New Knowledge)")
        with st.form("add_knowledge_form"):
            new_text = st.text_area("内容 (Content)", height=150, placeholder="在此输入知识库内容...")
            category = st.selectbox("分类 (Category)", ["info", "rule", "contact", "manual", "other"])
            submitted = st.form_submit_button("添加 (Add)")
            
            if submitted and new_text:
                try:
                    metadata = [{"source": "dashboard", "category": category}]
                    ks.add_texts([new_text], metadata)
                    st.success("✅ 添加成功！")
                except Exception as e:
                    st.error(f"添加失败: {e}")

with tab3:
    st.header("数据库统计 (Database Statistics)")
    try:
        count = active_collection.count()
        st.metric("总条目数 (Total Entries)", count)
        
        current_path = voiceprint_path if is_voiceprint else knowledge_path
        st.code(f"存储路径: {current_path}", language="bash")
        
        if is_voiceprint:
             st.markdown("### 声纹库详情\n- **向量**: 音频 Embeddings (通常为 192维)\n- **元数据**: 用户信息, 时间戳")
        else:
             st.markdown("### 知识库详情\n- **向量**: 文本 Embeddings\n- **元数据**: 来源 (Source), 分类 (Category)")
            
    except Exception as e:
        st.error(f"无法加载统计信息: {e}")
