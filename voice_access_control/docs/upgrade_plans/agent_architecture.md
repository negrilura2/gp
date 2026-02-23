# 🚀 系统升级规划：从“声纹门禁”到“智能管家 Agent”

## 1. 核心愿景
从单一的“身份验证（你是谁）”升级为“**身份感知 + 意图理解 + 主动执行（你是谁 + 你想做什么）**”。
技术架构从“文件上传 + 离线识别”升级为“**流式 WebSocket + 实时感知 + Agent 决策**”。

---

## 2. 架构变更对比

| 模块 | 当前版本 (As-Is) | 升级目标 (To-Be) | 技术栈关键点 |
| :--- | :--- | :--- | :--- |
| **交互方式** | HTTP POST 上传完整 WAV 文件 | **WebSocket 双向流式传输** | Django Channels 或 FastAPI WebSocket |
| **音频处理** | 存盘 -> 读取 -> 预处理 -> 识别 | **内存 Ring Buffer -> VAD 切片 -> 实时提取** | `collections.deque`, `webrtcvad` |
| **声纹存储** | 本地 `.npy` 文件 (文件系统) | **向量索引 (Vector Index)** | **FAISS** (HNSW 索引) 或 ChromaDB |
| **识别逻辑** | 1:1 或 1:N 暴力余弦相似度计算 | **ANN (近似最近邻) 向量检索** | FAISS `IndexHNSWFlat` |
| **语义理解** | 无 (仅验证身份) | **ASR (语音转文字) + LLM Agent** | **Faster-Whisper** + **LangChain** |
| **执行逻辑** | 硬编码 (开门/拒绝) | **Function Calling (工具调用)** | Agent 动态决策 (开门/报警/开灯) |

---

## 3. 详细技术方案

### 3.1 向量存储与检索 (Vector Store)
*   **现状**：用户注册后生成 `.npy`，验证时加载所有模板遍历计算。
*   **升级**：
    *   引入 **FAISS (Facebook AI Similarity Search)**。
    *   启动时：将所有用户的 Embedding 加载到内存构建 `IndexHNSWFlat` 索引。
    *   注册时：实时 add 向量到索引，并持久化索引文件。
    *   验证时：`index.search(query_vector, k=1)` 毫秒级返回最相似 ID。

### 3.2 流式处理流水线 (Streaming Pipeline)
用户端 (WebSocket) 每 100ms 发送二进制 Chunk：

1.  **VAD (Voice Activity Detection)**：
    *   过滤静音，只处理有效语音帧。
    *   累积有效语音达到窗口（如 1s - 3s）。
2.  **并行处理 (Parallel Processing)**：
    *   **分支 A (Identity)**：送入 ECAPA-TDNN 提取 Embedding -> FAISS 检索 -> 确认身份 (如 "User: Alice, Score: 0.85")。
    *   **分支 B (Intent)**：送入 Faster-Whisper -> Transcribe -> 文本 (如 "帮我开灯")。
3.  **Agent 决策 (Decision)**：
    *   Input: `Identity="Alice"`, `Text="帮我开灯"`, `Risk_Level="Low"`
    *   Prompt: "你是智能管家。用户 Alice (已认证) 说 '帮我开灯'。现有工具: [open_door, turn_on_light, call_police]。请决策。"
    *   Output: `Action: turn_on_light(room="living_room")`

### 3.3 Agent 定义 (LangChain)
*   **Tools (工具集)**：
    *   `open_door()`: 也就是原来的 `/api/verify` 成功后的逻辑。
    *   `control_device(device_name, action)`: 模拟智能家居 API。
    *   `emergency_alert(reason)`: 报警 API (当识别到“救命”、“有人跟踪”等关键词或情绪时)。
*   **Memory**: 记住多轮对话上下文（可选）。

---

## 4. 实施路线图 (Roadmap)

### 阶段一：向量化改造 (Vectorization) 🟢 **(Priority High)**
1.  引入 `faiss-cpu`。
2.  编写 `VectorStore` 类：封装 `add`, `search`, `save`, `load`。
3.  编写脚本：把现有 `data/voiceprints/*.npy` 迁移到 FAISS 索引中。
4.  改造 `VoiceService`：使用 `VectorStore` 替换原来的字典遍历。

### 阶段二：流式接口与 VAD (Streaming) 🟡
1.  在 AI Service (FastAPI) 中增加 WebSocket 接口 `/ws/stream`。
2.  实现 `AudioBuffer` 处理类：接收 bytes，缓冲，VAD 切割。
3.  前端实现：使用 `AudioWorklet` 或 `MediaRecorder` 实时发送 chunk。

### 阶段三：ASR 与 Agent 集成 (Intelligence) 🔴
1.  集成 `faster-whisper` 到 AI Service。
2.  引入 `langchain`，定义 Tools。
3.  连接逻辑：Voice 结果 + ASR 结果 -> Agent -> 执行。

---

## 5. 依赖变更
*   `faiss-cpu`
*   `faster-whisper`
*   `langchain`
*   `webrtcvad` (可选，或简单的能量检测)
*   `websockets` (FastAPI 自带支持)
