# 🗺️ 声纹识别智能门禁系统 — 终极升级路线图

> **本文档是唯一权威的升级参考。**
> 原 `docs/upgrade_plans/` 下 11 个散落规划文档已于 2026-02-26 合并至本文件后删除。

---

## 一、总体战略：三线并行，分层推进

```
┌──────────────────────────────────────────────────────────┐
│                  应用交互层 (Application)                  │
│   前端 UI · Agent 决策 · WebSocket 实时交互 · 设备模拟器    │
├──────────────────────────────────────────────────────────┤
│                  核心服务层 (Core Services)                │
│   声纹引擎 · STT 引擎 · 向量检索 · 分数归一化 · 特征对比    │
├──────────────────────────────────────────────────────────┤
│                  基础设施层 (Infrastructure)               │
│   Docker · CI/CD · 数据库 · Redis · 消息队列 · 日志监控    │
└──────────────────────────────────────────────────────────┘
```

**原则**：先稳固地基（数据层、容器化），再构建能力（STT、流式处理），最后串联场景（Agent 决策）。

---

## 二、深度学习升级路线（AI 核心）

目标：将毕设 AI 部分从"训练一个模型"升级为"一套可解释、可展示的声纹研究链路"。

### Level 1：基线模型建立 ✅ 已完成
- ECAPA-TDNN 模型训练与收敛验证
- 训练曲线（Loss/Accuracy）记录

### Level 2：特征对比实验 ✅ 已完成
- MFCC / Log-Mel Spectrogram / MFCC+Δ 三组对比训练
- 不同声学特征对识别性能的影响分析

### Level 3：噪声鲁棒性实验 ✅ 已完成
- 白噪声测试（Clean / 20dB / 10dB / 0dB / -5dB）
- 真实环境噪声测试（Street.wav）
- 鲁棒性曲线图已归档至 `reports/noise_tests/`

### Level 4：训练策略实验 🔄 代码就绪
- Early Stopping vs 固定 Epoch 对比
- EER 评估频率优化（`--eer_interval` 参数）
- Windows DataLoader 性能优化已完成

### Level 5：嵌入空间可视化 ⏳ 待执行
- 提取 192 维 speaker embedding → t-SNE / UMAP 降维 → 2D 聚类图
- 脚本入口：`scripts/analysis/plot_embedding.py`
- 输出：`reports/plots/embedding/tsne_{feature_type}.png`

### Level 6：分数归一化 ⏳ 待执行
- 实现 Z-Norm / T-Norm / S-Norm
- 在 `scripts/evaluate.py` 中增加 `--score_norm` 参数
- 对比实验：原始 cosine vs Z-Norm vs S-Norm 的 EER/FRR 稳定性
- 集成到 `VoiceService.verify()` 中，通过配置开关控制

---

## 三、系统工程化升级路线

### Phase 1：地基固化 🟢 部分完成

| 任务 | 状态 | 说明 |
|:---|:---:|:---|
| ChromaDB 向量数据库集成 | ✅ | 替代 .npy 文件遍历 |
| AI Service 独立化（FastAPI） | ✅ | Django 通过 HTTP 调用 AI 能力 |
| Docker Compose 基础编排 | ✅ | DB + AI Service + Backend + Frontend |
| 数据迁移脚本验证 | ⏳ | 需要验证 Chroma 迁移完整性 |

### Phase 2：核心工程化 🟡 规划中

| 任务 | 优先级 | 说明 |
|:---|:---:|:---|
| Redis 引入 | ⭐⭐⭐ | 登录状态、门禁缓存、限流计数 |
| JWT 统一鉴权 | ⭐⭐⭐ | JWT + Redis blacklist |
| 消息队列解耦（Kafka/Redpanda） | ⭐⭐⭐⭐ | API → Producer → Queue → AI Consumer |
| Celery 异步任务 | ⭐⭐⭐ | 日志写入、延迟任务、数据清理 |

### Phase 3：系统治理 🔴 远期规划

| 任务 | 说明 |
|:---|:---|
| API Gateway（Nginx） | 统一入口、限流、路由 |
| Prometheus + Grafana | 指标采集与可视化 |
| 请求链路追踪（trace_id） | OpenTelemetry 轻量用法 |
| Snowflake 全局 ID | 门禁记录 ID、事件 ID |

### Phase 4：云原生能力 🔵 可选加分

| 任务 | 说明 |
|:---|:---|
| CI/CD（GitHub Actions） | push → test → build → deploy |
| Kubernetes 基础部署 | Deployment + Service + HPA |
| 模型版本管理 | model-v1/v2 + A/B Testing |
| SLO/Error Budget | 可靠性工程实践 |

**执行顺序**：AI 服务拆分 ① → Docker ② → Redis ③ → MQ ④ → Celery ⑤ → Gateway ⑥ → CI/CD ⑦ → K8s ⑧

---

## 四、Agent 智能化升级路线

目标：从"身份验证(你是谁)"升级为"身份感知 + 意图理解 + 主动执行"。

### 阶段一：向量化改造 ✅ 已完成
- ChromaDB 替代 .npy 遍历
- VectorStore 封装 add / search / save / load

### 阶段二：感知能力构建 ✅ 基础完成
- STT 引擎集成（Faster-Whisper） ✅
- WebSocket 流式端点 `/ws/audio` ✅
- VAD 语音活动检测（webrtcvad） ✅
- AudioBuffer 环形缓冲区 ✅

### 阶段三：Agent 决策 ✅ 基础完成
- LangChain Agent + DeepSeek V3 集成 ✅
- Tools 定义：open_door / turn_on_light / alert_police ✅
- 身份感知 Prompt Template ✅
- 多模态融合流程（Voice + STT → Agent → Action） ✅

### 待优化项
- [ ] Agent Memory（多轮对话上下文）
- [ ] 情绪识别与异常关键词检测
- [ ] 更多 Tools 扩展（设备控制、访客管理）

---

## 五、前端体验升级路线

### 当前状态
- Vue.js 3 + Element Plus + Vite ✅
- 页面：VoiceVerify / AdminDashboard / AdminLogin / UserProfile ✅
- 管理后台（用户管理、日志查看、ROC 图表展示） ✅

### 规划中
- [ ] 动态波形图（Canvas + WebAudio）：录音时实时展示
- [ ] ECharts 数据可视化 Dashboard：验证统计、声纹分布
- [ ] 嵌入空间聚类图（t-SNE）展示
- [ ] 设备模拟器 UI（IoT 心跳 + 音频流模拟）
- [ ] 验证通过/失败动画与音效

---

## 六、代码重构路线（技术债清理）

详见 `docs/refactoring_roadmap.md`，核心任务：

### 阶段一：配置与核心引擎统一 ⚠️ 优先
1. **配置中心** (`voice_engine/config.py`)：已有，需要进一步统一所有硬编码常量
2. **特征提取统一**：消灭 4 处重复的特征提取逻辑，统一到 `voice_engine/` 中
3. **模型加载统一**：消灭 Django `model_loader.py` 与 `voice_engine/service.py` 的重复逻辑

### 阶段二：模型元数据
- 训练时保存 `model_config.json`（feature_type, n_mels, embedding_dim 等）
- 加载时自动读取配套 JSON，替代靠文件名/维度猜测

### 阶段三：Trainer 拆分
- 将评估工具函数移至 `voice_engine/metrics.py`（已完成）
- Trainer 只保留训练逻辑

---

## 七、技术栈一览（终态）

| 层级 | 技术 | 状态 |
|:---|:---|:---:|
| Frontend | Vue.js 3 + Element Plus + Vite | ✅ |
| Backend (API) | Django REST Framework | ✅ |
| AI Service | FastAPI + PyTorch (ECAPA-TDNN) | ✅ |
| STT Engine | Faster-Whisper | ✅ |
| Agent | LangChain + DeepSeek V3 | ✅ |
| Vector DB | ChromaDB | ✅ |
| Database | SQLite (dev) / MySQL (prod) | ✅ |
| Cache | Redis | ⏳ 规划中 |
| Message Queue | Kafka / Redpanda | ⏳ 规划中 |
| Async Tasks | Celery | ⏳ 规划中 |
| Gateway | Nginx | ⏳ 规划中 |
| Container | Docker + Docker Compose | ✅ |
| Orchestration | Kubernetes | ⏳ 可选 |
| CI/CD | GitHub Actions | ⏳ 规划中 |

---

## 八、Sprint 行动计划

> 原则：**修 Bug → 补实验 → 稳工程 → 写论文**

### Sprint 1：技术债清理（最高优先级）
| 任务 | 预期结果 |
|:-----|:---------|
| 特征提取逻辑统一到 `voice_engine/` | 修改任何特征参数只需改一处 |
| 模型元数据（训练时保存 `model_config.json`） | 模型加载自描述，不再靠猜 |
| 消灭配置硬编码 | `config.py` 成为唯一配置源 |

### Sprint 2：深度学习实验闭环（论文核心）
| 任务 | 预期结果 |
|:-----|:---------|
| Level 4 训练策略实验 | Baseline vs Early Stopping 对比数据 |
| Level 5 嵌入空间可视化 | t-SNE 聚类图生成 |
| Level 6 分数归一化 | Z-Norm/S-Norm EER 对比 |

### Sprint 3：工程化与前端打磨（答辩展示）
| 任务 | 预期结果 |
|:-----|:---------|
| Docker Compose 端到端验证 | `docker compose up` 全服务健康 |
| 前端 ECharts Dashboard | 数据可视化图表展示 |
| Agent 端到端演示流程 | 答辩可流畅演示 |

### Sprint 4：论文 & 交付（毕设收尾）
| 任务 | 预期结果 |
|:-----|:---------|
| 毕业设计说明书 | 规范格式，含全部实验数据 |
| 外文翻译 + 原文 | ≥ 3000 字 |
| 答辩 PPT + 演示脚本 | 含应急方案 |

---

## 九、风险控制原则

1. **接口兼容**：开发新接口时必须保留旧 HTTP `/enroll` 和 `/verify`
2. **开关控制**：Django 中的 `ENABLE_AGENT_MODE` 开关，关闭时走旧逻辑
3. **数据双写**：过渡期注册声纹同时写 `.npy` 和 Chroma，确保可回滚
4. **不要全铺开**：选择 3-4 个高价值升级做到闭环，优于铺开 10+ 个半成品

---

> 📌 **本文档最后更新**：2026-02-26
> 如需修改升级优先级或新增路线，请直接编辑本文件，不要再新建散落文档。
