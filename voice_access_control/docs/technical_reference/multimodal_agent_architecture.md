# 多模态 AI 架构与 Agent 设计文档

本文档详细总结了本项目中涉及的多模态 AI 框架、向量模型以及 Agent 架构的设计思路、核心原理及代码实现逻辑。

---

## 1. 系统架构概览 (System Architecture)

本项目构建了一个集成了**声纹识别 (Voiceprint Recognition)**、**语音转写 (STT)** 和 **意图理解 (NLU)** 的多模态智能安防系统。系统通过 WebSocket 接收实时音频流，并行处理身份验证与指令解析，最终由 Agent 决策执行。

### 核心组件
1.  **Audio Stream Processor**: 负责音频流的缓冲、VAD（语音活动检测）切分。
2.  **Voice Encoder (ECAPA-TDNN)**: 将音频片段编码为 192 维度的声纹向量。
3.  **Vector Store (ChromaDB)**: 存储与检索用户声纹特征，支持高效的相似度搜索。
4.  **STT Engine (Faster-Whisper)**: 将语音转换为文本。
5.  **Agent Core (LangChain + DeepSeek)**: 结合用户身份（Who）与指令内容（What），进行语义理解并调用工具（Function Calling）。

---

## 2. 音频流处理与多模态输入 (Audio Stream & Multi-modal Input)

### 设计思路
为了实现低延迟的实时交互，系统放弃了传统的文件上传模式，采用 WebSocket 流式传输。核心挑战在于如何从连续的音频流中切分出有效的语音片段（Voice Activity Detection, VAD）。

### 核心代码：`stream_processor.py`
*   **Rolling Buffer**: 维护一个环形缓冲区，处理 30ms 的音频帧。
*   **VAD Logic**: 使用 `webrtcvad` 检测每一帧是否为人声。
*   **Trigger Mechanism**:
    *   当连续 `N` 帧为人声时，触发“开始记录”状态。
    *   当连续 `M` 帧为静音时，触发“结束记录”状态，将缓冲区的音频打包为一个 `Segment`。

```python
# 代码片段示意
class AudioBuffer:
    def process(self, chunk: bytes) -> list[bytes]:
        # 1. 填充缓冲区
        # 2. VAD 检测当前帧
        # 3. 状态机判断：
        #    - Triggered: 收集语音帧
        #    - Not Triggered: 丢弃静音帧（保留少量 Padding）
        # 4. 返回切分好的 wav 数据块
```

---

## 3. 向量模型与声纹识别 (Vector Model & Voiceprint)

### 核心原理
声纹识别本质上是一个**度量学习 (Metric Learning)** 问题。我们将不定长的语音片段映射到一个固定维度的超球面上，使得同一个人（Intra-class）的向量距离尽可能近，不同人（Inter-class）的向量距离尽可能远。

### 模型架构：ECAPA-TDNN
*   **Input**: 80-dim Log-Mel Spectrogram.
*   **Backbone**: ECAPA-TDNN (Emphasized Channel Attention, Propagation and Aggregation in TDNN).
    *   引入了 SE-Block (Squeeze-and-Excitation) 进行通道注意力加权。
    *   使用多尺度特征聚合（Multi-scale Feature Aggregation）。
*   **Output**: 192-dim Embedding Vector.
*   **Loss Function**: AAM-Softmax (Additive Angular Margin Softmax)，优化余弦距离。

### 向量数据库：ChromaDB (`vector_store.py`)
为了支持快速检索，我们引入了 ChromaDB 替代原有的 `.npy` 文件遍历。
*   **Collection**: `voice_prints`
*   **Embedding Function**: 自定义适配器，直接存入 ECAPA-TDNN 提取的向量。
*   **Search**: 使用 HNSW 算法进行近似最近邻搜索 (ANN)，计算 Cosine Similarity。
*   **Threshold**: 设定阈值（如 0.75），超过该相似度则认为身份验证通过。

```python
# vector_store.py 核心逻辑
class VectorStore:
    def search(self, embedding, n_results=1):
        # 查询最相似的声纹
        results = self.collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=n_results
        )
        # 返回 user_id 和 distance
```

---

## 4. 语音转写 (Speech-to-Text)

### 设计思路
为了让 Agent 理解用户意图，必须将语音转化为文本。考虑到即时性与部署成本，选用 `faster-whisper`（基于 CTranslate2 加速的 Whisper 模型）。

### 实现细节 (`stt_service.py`)
*   **Model**: `tiny` 或 `base` 模型（兼顾速度与精度）。
*   **Compute Type**: `int8` 量化，大幅降低 CPU 推理延迟。
*   **Beam Size**: 设置为 5，提高解码准确率。

---

## 5. Agent 架构 (LangChain + DeepSeek)

### 设计思路
Agent 是系统的“大脑”，它不再是简单的关键词匹配，而是基于**大语言模型 (LLM)** 的推理能力。
我们采用 **ReAct (Reasoning + Acting)** 范式，但通过 **Tool Calling (Function Calling)** 进行了简化与强化。

### 核心组件 (`agent_service.py`)

#### 1. 上下文感知 (Context Awareness)
Agent 不仅接收文本指令，还接收**用户身份信息**。这是本系统的一大特色——**“基于身份的权限控制 Agent”**。
*   **Input**: `Text` (e.g., "Open the door") + `User Context` (e.g., "User: Admin, Score: 0.92").
*   **System Prompt**:
    ```text
    You are a smart home security assistant.
    Current user identity: {user_identity} (Confidence: {confidence}).
    If the user is unknown or confidence is low, be cautious about security-critical actions like opening doors.
    ```

#### 2. 工具集 (Tools)
通过 LangChain 的 `@tool` 装饰器定义可被 LLM 调用的函数：
*   `open_door(user_name)`: 开门（需鉴权）。
*   `turn_on_light(location)`: 开灯（非敏感）。
*   `alert_police(reason)`: 报警（高危）。

#### 3. 推理引擎 (DeepSeek V3)
使用 DeepSeek API 作为推理后端。DeepSeek 在指令遵循和代码/JSON 生成方面表现优异，能够准确输出 Tool Call 所需的 JSON 结构。

### 代码实现逻辑
```python
# agent_service.py
class AgentService:
    def __init__(self):
        # 初始化 LLM (DeepSeek)
        self.llm = ChatOpenAI(model="deepseek-chat", ...)
        # 绑定 Tools
        self.tools = [open_door, turn_on_light, alert_police]
        # 创建 Agent Executor
        self.agent_executor = create_tool_calling_agent(self.llm, self.tools, self.prompt)

    async def process_command(self, text, user_context):
        # 注入身份上下文
        return await self.agent_executor.ainvoke({
            "input": text,
            "user_identity": user_context['user'],
            "confidence": user_context['score']
        })
```

---

## 6. 多模态融合流程 (Integration Workflow)

在 `ai_app.py` 的 WebSocket Endpoint 中，我们将上述模块串联起来，形成闭环：

1.  **Receive**: 从 WebSocket 接收音频 Chunk。
2.  **Buffer & VAD**: `stream_processor` 积攒音频直至检测到完整语音段。
3.  **Parallel Processing** (并行处理):
    *   **Task A (Vision/Voice)**: 调用 `VoiceService` -> `ECAPA-TDNN` -> `ChromaDB`，返回 `(User, Score)`。
    *   **Task B (Audio/Text)**: 调用 `STTService` -> `Whisper`，返回 `Text`。
4.  **Agent Reasoning**:
    *   将 `Text` 和 `(User, Score)` 输入 `AgentService`。
    *   Agent 判断是否执行操作（如：如果是陌生人，即使说了“开门”，Agent 也会拒绝）。
5.  **Response**: 将 `Identity`, `Text`, `Agent Action` 打包回传给前端。

### 流程图解
```mermaid
graph TD
    A[WebSocket Input] --> B[AudioBuffer + VAD]
    B -- Segment --> C{Parallel Tasks}
    C -->|Voice Path| D[ECAPA-TDNN Encoder]
    D --> E[ChromaDB Vector Search]
    E --> F[Identity: User + Score]
    
    C -->|Text Path| G[Faster-Whisper STT]
    G --> H[Text Content]
    
    F --> I[Agent Core (DeepSeek)]
    H --> I
    
    I --> J{Decision}
    J -->|Authorized| K[Call Tool: open_door]
    J -->|Unauthorized| L[Refuse Action]
    
    K --> M[Final Response]
    L --> M
```
