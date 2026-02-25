# 🔐 Voice Access Control — 声纹识别智能门禁系统

> 基于 **ECAPA-TDNN** 声纹识别 + **LangChain Agent** 意图理解的多模态智能门禁平台。
> 涵盖深度学习模型训练/推理、实时音频流处理、向量数据库检索、Agent 决策执行、前后端联调与 Docker 容器化部署。

---

## 📐 系统架构

```
                          ┌─────────────────────┐
                          │   Vue.js Frontend   │
                          │  (Element Plus/Vite) │
                          └──────────┬──────────┘
                                     │ HTTP / WebSocket
                          ┌──────────▼──────────┐
                          │   Django Backend    │
                          │  (REST API + Admin) │
                          └──────────┬──────────┘
                                     │ HTTP
                          ┌──────────▼──────────┐
                          │  FastAPI AI Service  │
                          │   (voice_engine)     │
                          ├─────────────────────┤
                          │ ┌─────┐  ┌────────┐ │
                          │ │ECAPA│  │Whisper │ │
                          │ │TDNN │  │ (STT)  │ │
                          │ └──┬──┘  └───┬────┘ │
                          │    │         │      │
                          │ ┌──▼─────────▼────┐ │
                          │ │ LangChain Agent  │ │
                          │ │  (DeepSeek V3)   │ │
                          │ └─────────────────┘ │
                          └──────────┬──────────┘
                      ┌──────────────┼──────────────┐
               ┌──────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
               │  ChromaDB   │ │  SQLite  │ │   Redis     │
               │ (向量存储)   │ │ (MySQL)  │ │  (规划中)    │
               └─────────────┘ └──────────┘ └─────────────┘
```

### 多模态处理流程

```
用户音频流 (WebSocket)
    │
    ▼
AudioBuffer + VAD 语音切分
    │
    ├──── 声纹路径 ──→ ECAPA-TDNN → ChromaDB 检索 → 身份识别 (Who?)
    │
    ├──── 语音路径 ──→ Faster-Whisper → 文本转录 (What?)
    │
    └──── Agent 路径 ──→ LangChain (身份 + 意图) → Tool Calling → 执行动作
                         (开门 / 开灯 / 报警 / 拒绝)
```

---

## 📁 项目目录结构

```
voice_access_control/
├── voice_engine/            # 🧠 AI 核心引擎 (library 层，不直接运行)
│   ├── ai_app.py            #    FastAPI 服务入口 (HTTP + WebSocket)
│   ├── service.py           #    VoiceService 单例 (enroll/verify/embedding)
│   ├── ecapa_tdnn.py        #    ECAPA-TDNN 模型定义
│   ├── trainer.py           #    模型训练器 (config 驱动)
│   ├── dataset.py           #    数据集加载
│   ├── losses.py            #    AAM-Softmax 损失函数
│   ├── metrics.py           #    评估工具 (EER/minDCF/ROC/Score Hist)
│   ├── config.py            #    全局配置中心 (SAMPLE_RATE, N_MELS, ...)
│   ├── vector_store.py      #    ChromaDB 向量存储封装
│   ├── agent_service.py     #    LangChain Agent + DeepSeek 集成
│   ├── stt_service.py       #    Faster-Whisper STT 服务
│   └── stream_processor.py  #    音频流 VAD 处理 (Ring Buffer)
│
├── scripts/                 # 🚀 可执行入口 (entrypoint 层)
│   ├── train.py             #    训练入口: python -m scripts.train --config ...
│   ├── evaluate.py          #    评估入口: python -m scripts.evaluate --config ...
│   ├── analysis/            #    可视化分析脚本
│   │   └── plot_embedding.py
│   ├── audio/               #    音频录制与交互验证
│   └── data/                #    数据预处理与特征提取
│
├── backend/                 # 🌐 Django 后端
│   ├── api/
│   │   ├── views/           #    拆分后的视图: auth/voice/admin/stats/logs/roc/users
│   │   ├── models.py        #    数据模型 (User, VoiceProfile, VerifyLog)
│   │   ├── serializers.py   #    DRF 序列化器
│   │   ├── model_loader.py  #    模型加载封装 (调用 AI Service)
│   │   └── urls.py          #    API 路由
│   └── manage.py
│
├── frontend/                # 🎨 Vue.js 前端
│   └── src/
│       ├── views/           #    页面: VoiceVerify / AdminDashboard / AdminLogin / UserProfile
│       ├── api.js           #    API 调用封装
│       └── router.js        #    路由配置
│
├── configs/                 # ⚙️ 实验配置 (YAML 驱动)
│   ├── ecapa.yaml           #    ECAPA-TDNN 训练参数
│   ├── data.yaml            #    数据预处理参数
│   ├── eval.yaml            #    评估参数
│   └── analysis.yaml        #    分析参数
│
├── data/                    # 💾 数据目录
│   ├── chroma_db/           #    ChromaDB 向量数据库文件
│   ├── voiceprints/         #    声纹模板 (.npy)，前端可视化依赖
│   ├── processed/           #    预处理后的音频
│   └── raw/                 #    原始音频数据
│
├── reports/                 # 📊 实验结果输出
│   ├── plots/               #    图表 (ROC/EER/噪声曲线/聚类图)
│   ├── metrics.json         #    评估指标
│   ├── noise_tests/         #    噪声鲁棒性测试结果
│   └── score_norm/          #    分数归一化对比结果
│
├── docs/                    # 📚 项目文档
│   ├── UPGRADE_ROADMAP.md   #  ⭐ 统一升级路线图 (唯一权威)
│   ├── technical_reference/ #    技术架构文档
│   └── progress_reports/    #    进展报告
│
├── docker-compose.yml       # 🐳 容器编排 (DB + AI + Backend + Frontend)
├── Dockerfile               #    后端/AI 服务镜像
├── requirements.txt         #    Python 依赖
├── setup.py                 #    包化安装 (pip install -e .)
├── .env.local               #    本地环境变量
└── .env.docker              #    Docker 环境变量
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 版本/说明 |
|:---|:---|:---|
| **语言** | Python | 3.9.18 |
| **深度学习** | PyTorch + ECAPA-TDNN | 轻量实现，192 维 embedding |
| **损失函数** | AAM-Softmax | 优化余弦角度间距 |
| **向量数据库** | ChromaDB | HNSW 近似最近邻检索 |
| **STT** | Faster-Whisper | CTranslate2 加速，int8 量化 |
| **Agent** | LangChain + DeepSeek V3 | Tool Calling + ReAct 范式 |
| **后端** | Django REST Framework | API + Admin + ORM |
| **AI 服务** | FastAPI | HTTP + WebSocket 双协议 |
| **前端** | Vue.js 3 + Element Plus | Vite 构建 |
| **容器化** | Docker + Docker Compose | MySQL + Redis + AI + Backend + Frontend |
| **音频处理** | scipy + torchaudio + webrtcvad | 去 librosa 化解决 Windows 兼容性 |

---

## 📈 项目进度总览

### ✅ 已完成

| 模块 | 内容 |
|:---|:---|
| **深度学习 Level 1-3** | 基线模型训练、特征对比实验（MFCC/LogMel/MFCC+Δ）、噪声鲁棒性实验 |
| **声纹引擎** | VoiceService 单例、注册/验证流程、ChromaDB 向量存储集成 |
| **AI Service** | FastAPI 独立服务，HTTP + WebSocket 双端点 |
| **STT 服务** | Faster-Whisper 集成，CUDA 自动降级到 CPU |
| **Agent** | LangChain + DeepSeek 集成，Tool Calling（开门/开灯/报警） |
| **流式处理** | WebSocket `/ws/audio`、VAD 切分、Ring Buffer、并行处理 |
| **后端** | Django REST API（enroll/verify/管理接口），Views 模块化拆分 |
| **前端** | Vue.js 4 页面（录音验证 / 管理后台 / 登录 / 用户资料） |
| **Docker** | docker-compose 编排 5 个服务 (DB/Redis/AI/Backend/Frontend) |
| **评估体系** | EER/minDCF/ROC 曲线生成、阈值评估工具 |
| **工程规范** | setup.py 包化、.gitignore、模块化目录重构 |

### 🔄 进行中

| 模块 | 内容 |
|:---|:---|
| **Level 4 训练策略** | Early Stopping vs 固定 Epoch 对比实验（代码已就绪） |
| **代码重构** | 特征提取逻辑统一、配置中心完善 |

### ⏳ 待完成

| 模块 | 优先级 | 内容 |
|:---|:---:|:---|
| **Level 5 可视化** | 🔴 高 | t-SNE 聚类图脚本与结果 |
| **Level 6 归一化** | 🔴 高 | Z-Norm/S-Norm 实现与对比实验 |
| **论文/文档** | 🔴 高 | 毕业设计说明书、外文翻译、开题/中期/最终报告 |
| **前端可视化** | 🟡 中 | ECharts Dashboard、动态波形图 |
| **Docker 验证** | 🟡 中 | 确认 docker compose up 端到端跑通 |
| **数据库切换** | 🟡 中 | SQLite → MySQL 迁移验证 |
| **认证鉴权** | 🟡 中 | JWT + Redis 统一鉴权 |

---

## ⚠️ 已知问题与技术债

### 🐛 待修复问题

| 问题 | 严重性 | 说明 |
|:---|:---:|:---|
| **WebSocket Windows 兼容** | 🟡 | Ctrl+C 退出问题已修复（CancelledError + run_in_executor），但 Windows 下仍需注意 |
| **STT CUDA 依赖** | 🟡 | cublas64_12.dll 缺失时已实现自动降级到 CPU，但 GPU 路径需验证 |

> **说明**：前端声纹可视化依赖 `data/voiceprints/*.npy` 文件，该数据现已纳入版本控制，非 Bug。

### 💩 技术债（"屎山"部分）

#### 1. 特征提取逻辑冗余（DRY 原则严重违反）
MFCC/LogMel/Delta 的提取逻辑散落在 **4 个独立文件** 中，且实现不一致：

| 位置 | 文件 | 问题 |
|:---|:---|:---|
| 训练数据 | `scripts/data/feature_extraction.py` | 使用 python_speech_features，无预加重 |
| 注册/验证 | `voice_engine/service.py` | 独立重实现，有预加重和归一化 |
| 噪声测试 | `scripts/eval/noise_robustness.py` | 第三套实现，补丁式修复 |
| 后端 | `backend/api/model_loader.py` | 硬编码特征推断，与引擎重复 |

**风险**：修改一个特征参数（如 `n_mels`）需同时改 4 个文件，极易漏改。

#### 2. 配置硬编码（Magic Numbers）
- `SAMPLE_RATE = 16000`、`n_mels=40` 等散落在各脚本头部
- 路径（如 `data/features`、`models/ecapa_best.pth`）在脚本中随处硬编码
- 已有 `voice_engine/config.py` 但未被所有模块统一引用

#### 3. 模型加载逻辑脆弱
- 依靠文件名或权重维度猜测模型类型（`mfcc` vs `logmel`），训练新参数模型时会误判
- Django `model_loader.py` 和 `voice_engine/service.py` 存在加载逻辑重复

#### 4. ~~文档散乱~~ ✅ 已修复
- 原 `docs/upgrade_plans/` 下 11 个重叠文档已合并为 `docs/UPGRADE_ROADMAP.md`，旧文件已删除

---

## 🚀 快速上手

### 环境准备

```bash
# 1. 创建 conda 环境
conda create -n voice_access python=3.9.18 -y
conda activate voice_access

# 2. 安装项目包（使 import voice_engine / scripts 可用）
cd voice_access_control
pip install -e .

# 3. 安装依赖
pip install -r requirements.txt

# 4. PyTorch (根据 GPU 选择)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Docker 一键启动

```bash
docker compose up --build
# Backend:  http://localhost:8000
# AI Service: http://localhost:9000
# Frontend: http://localhost:5173
```

### 本地开发

```bash
# 启动 AI 服务
python -m voice_engine.ai_app

# 启动 Django 后端
cd backend && python manage.py migrate && python manage.py runserver

# 启动前端
cd frontend && npm install && npm run dev
```

---

## 📋 常用命令

```bash
# 数据预处理
python -m scripts.data.preprocess --config configs/data.yaml

# 特征提取
python -m scripts.data.feature_extraction --config configs/data.yaml

# 模型训练
python -m scripts.train --config configs/ecapa.yaml

# 模型评估 (EER/ROC)
python -m scripts.evaluate --config configs/eval.yaml --score_norm none

# 嵌入可视化 (t-SNE)
python -m scripts.analysis.plot_embedding --config configs/analysis.yaml

# API 示例
curl -X POST -F "user_id=alice" -F "files=@/path/1.wav" http://127.0.0.1:8000/api/enroll/
curl -X POST -F "file=@/path/test.wav" -F "threshold=0.70" http://127.0.0.1:8000/api/verify/
```

---

## 📚 文档索引

| 文档 | 说明 |
|:---|:---|
| [UPGRADE_ROADMAP.md](docs/UPGRADE_ROADMAP.md) | ⭐ 统一升级路线图（深度学习 + 工程化 + Agent + 前端） |
| [multimodal_agent_architecture.md](docs/technical_reference/multimodal_agent_architecture.md) | 多模态 AI 框架与 Agent 架构设计 |
| [refactoring_roadmap.md](docs/refactoring_roadmap.md) | 代码审查与重构规划 |
| [troubleshooting_logmel_hang.md](docs/troubleshooting_logmel_hang.md) | LogMel 卡死问题排查记录 |
| [progress_report.md](docs/progress_reports/progress_report.md) | 项目进展报告 |

---

## 🎓 毕设交付清单

- [ ] 开题报告（含参考文献 ≥ 20 篇）
- [ ] 中期报告
- [ ] 外文翻译与原文（≥ 3000 字）
- [ ] 源代码与模型权重（`models/*.pth`）
- [ ] 系统演示（后端 API + 前端 UI）
- [ ] 毕业设计说明书（规范格式）
- [ ] 实验数据（ROC/EER/训练曲线/噪声曲线/超参细节）
- [ ] 答辩 PPT 与现场演示脚本

---

> 📌 最后更新：2026-02-26 | 如有问题请参阅 [文档索引](#-文档索引) 或查看 `docs/` 目录
