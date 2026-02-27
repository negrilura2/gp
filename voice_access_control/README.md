# 🔐 Voice Access Control — 声纹识别智能门禁系统

> **Industrial-Grade Multimodal AI Security Platform**
> 
> 基于 **ECAPA-TDNN** 声纹识别 + **LangChain Agent** 意图理解的混合智能门禁系统。
> 集成实时音频流处理、边缘/云端协同决策、向量数据库检索与全栈容器化部署。

---

## 📐 系统架构 (System Architecture)

本项目采用 **微服务架构**，核心组件完全解耦，通过 Docker Compose 统一编排。

### 1. 整体拓扑图

```mermaid
graph TD
    User["用户 (Browser/App)"] -->|WebSocket 音频流| AIService
    User -->|HTTP 请求| Nginx[Nginx Gateway]
    
    Nginx --> Frontend["前端容器 (Vue3 + Vite)"]
    Nginx --> Backend["后端容器 (Django REST)"]
    
    subgraph "Core AI Engine"
        AIService[AI Service (FastAPI)]
        AIService -->|VAD & STT| Whisper[Faster-Whisper]
        AIService -->|Embedding| ECAPA[ECAPA-TDNN]
        AIService -->|Reasoning| Agent[LangChain + DeepSeek]
        AIService -->|Vector Store| ChromaDB[ChromaDB]
    end
    
    subgraph "Data Persistence"
        Backend --> MySQL["(MySQL 8.0)"]
        AIService -.-> Redis["(Redis 缓存)"]
    end
```

### 2. 混合智能处理流程 (Hybrid Intelligence)

系统采用 **Edge-Cloud Synergy** 策略，兼顾低延迟与高智能：

*   **L1: 边缘端 (Local NLU)**：毫秒级响应高频指令（如“开门”、“关灯”），纯本地规则匹配，无需消耗云端 Token。
*   **L2: 云端 (Cloud Agent)**：处理复杂意图（如“小区物业电话是多少”、“我想改密码”），调用 RAG 知识库或大模型推理。

```
用户音频流 (WebSocket)
    │
    ▼
AudioBuffer + VAD (Mode 3) 语音切分
    │
    ├──── 声纹路径 ──→ ECAPA-TDNN (192-dim) → ChromaDB 检索 → 身份确认
    │
    ├──── 语音路径 ──→ Faster-Whisper (int8) → 文本转录 (ASR)
    │
    └──── 智能决策 (Decision Maker)
            │
            ├─ [L1: Edge NLU] ──→ 立即执行 (Latency < 50ms)
            │
            └─ [L2: Cloud Agent] ──→ DeepSeek V3 + RAG (Latency ~1.5s)
```

---

## ✨ 核心功能 (Key Features)

### 🧠 AI 核心能力
- **高精度声纹识别**：基于 ECAPA-TDNN 模型，支持 AAM-Softmax 训练，具备抗噪鲁棒性。
- **混合意图理解**：Local NLU + LLM Agent 双引擎，支持 Tool Calling（开门/报警/查询）。
- **RAG 知识库**：内置 ChromaDB 向量检索，支持家庭/社区规则智能问答。
- **流式交互**：WebSocket 实时音频流处理，支持流式转录与实时反馈。

### 💻 全栈工程化
- **现代化前端**：Vue 3 + Element Plus + ECharts，响应式仪表盘设计。
- **稳健后端**：Django REST Framework，集成 JWT 鉴权与 RBAC 权限管理。
- **工业级监控**：支持意图分布统计、决策来源分析、系统延迟热力图及安全审计日志。
- **容器化部署**：提供生产级 Docker Compose 配置，支持 MySQL、Redis 等组件一键拉起。

---

## 🚀 快速开始 (Quick Start)

### 前置要求
- Python 3.9+
- Node.js 18+
- Docker & Docker Compose (推荐)
- NVIDIA GPU (可选，支持 CUDA 加速)

### 方式一：Docker 一键部署 (推荐)

```bash
# 1. 克隆仓库
git clone https://github.com/your-repo/voice_access_control.git
cd voice_access_control

# 2. 配置环境变量
cp .env.docker .env

# 3. 启动服务集群
docker compose up -d --build

# 访问地址:
# Frontend: http://localhost:5173
# Backend:  http://localhost:8000
# AI Docs:  http://localhost:9000/docs
```

### 方式二：本地开发模式

```bash
# 1. 启动 AI Service (核心引擎)
python -m voice_engine.ai_app

# 2. 启动 Django Backend
cd backend
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# 3. 启动 Vue Frontend
cd frontend
npm install
npm run dev
```

---

## 🛠️ 运维与监控

### 1. 智能监控仪表盘
登录后台 (http://localhost:5173/admin) 可查看：
- **实时意图分布**：用户指令类型占比统计。
- **决策来源分析**：边缘处理与云端 Agent 处理的效率对比。
- **性能分析**：全链路交互延迟监控。

### 2. 向量数据库管理
支持可视化管理 ChromaDB 中的声纹数据和知识库内容。

```bash
streamlit run tools/knowledge_dashboard.py
```

---

## 📁 目录结构说明

```
voice_access_control/
├── voice_engine/            # 🧠 AI 核心引擎 (FastAPI + Models)
│   ├── ai_app.py            #    服务入口 (HTTP/WS)
│   ├── service.py           #    声纹服务单例
│   ├── agent_service.py     #    LangChain Agent 实现
│   ├── nlu.py               #    本地 NLU 引擎
│   └── ecapa_tdnn.py        #    PyTorch 模型定义
│
├── backend/                 # 🌐 业务后端 (Django)
│   ├── api/                 #    REST API 实现
│   └── backend/             #    Django 项目配置
│
├── frontend/                # 🎨 用户前端 (Vue 3)
│   └── src/views/           #    仪表盘与验证页面
│
├── data/                    # 💾 持久化数据 (ChromaDB/Audio)
├── checkpoints/             # 📂 模型权重存储
├── configs/                 # ⚙️ 实验配置文件
├── scripts/                 # 🛠️ 训练、评估与数据脚本
└── docker-compose.yml       # 🐳 容器编排配置
```

---

## 📚 开发者文档

更多技术细节，请参考 `docs/` 目录：

- [📈 升级路线图 (Roadmap)](docs/UPGRADE_ROADMAP.md) - 项目演进规划与当前状态
- [🏗️ 多模态 Agent 架构](docs/technical_reference/multimodal_agent_architecture.md) - 核心设计思想
- [🧪 实验报告](docs/progress_reports/progress_report.md) - 模型性能测试数据

---

## 📜 许可证

MIT License © 2026 China netcom Team
