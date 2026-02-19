# 深度学习升级规划与进度追踪

根据《深度学习升级.md》文档，本项目将从单纯的“模型训练”升级为“系统化声纹研究”。以下是目前的进度与后续规划。

## 🎯 总体目标
将毕设项目伪装成一个“小型声纹研究项目”，通过六个层级的实验证明系统的有效性与工程价值。

---

## 📊 实验层级与进度

### LEVEL 1: 基线模型建立 (Baseline)
**目标**: 建立标准的 ECAPA-TDNN 训练基准，证明模型收敛。
- [x] 模型训练 (ECAPA-TDNN)
- [ ] 训练曲线图 (Loss/Accuracy) - *待确认是否已生成标准图表*
- [ ] 验证集评估 (EER/Accuracy)

### LEVEL 2: 特征对比实验 (Feature Contrast)
**目标**: 证明不同声学特征对识别性能的影响。
- [x] MFCC 模型训练
- [x] Log-Mel Spectrogram 模型训练
- [x] MFCC + Δ特征 模型训练
- [ ] 对比分析报告 (EER/Accuracy 表格)

### LEVEL 3: 噪声鲁棒性实验 (Noise Robustness)
**目标**: 验证系统在真实环境下的可用性（答辩核心亮点）。
- [x] 噪声测试脚本开发 (`scripts/eval/noise_robustness.py`)
- [x] 白噪声测试 (Clean/20dB/10dB/0dB/-5dB) - *已完成*
- [x] 真实环境噪声测试 (Street.wav) - *已完成*
- [x] 鲁棒性曲线图 (Accuracy vs Noise Level) - *已完成 (reports/archive/plots/noise/)*

### LEVEL 4: 训练策略实验 (Training Strategy)
**目标**: 展示研究思维，对比不同训练策略的效果。
- [ ] Early Stopping 实验设计
- [ ] 训练时间与最终性能对比分析

### LEVEL 5: 嵌入空间可视化 (Embedding Visualization)
**目标**: 直观展示声纹区分能力（t-SNE/PCA）。
- [ ] 开发可视化脚本 (`scripts/eval/plot_embedding.py`)
- [ ] 生成不同说话人的聚类图 (2D Scatter Plot)

### LEVEL 6: 分数归一化 (Score Normalization)
**目标**: 解决得分分布漂移问题，提升工业级稳定性。
- [ ] 实现 Z-Norm / T-Norm / S-Norm
- [ ] 验证 EER/FRR 稳定性提升
- [ ] 系统集成归一化模块

---

## 📅 下一步具体行动计划 (Updated)

1.  **补全可视化工具 (Level 5)** - **当前优先级最高**
    *   编写 `scripts/eval/plot_embedding.py`。
    *   提取测试集 embedding 并使用 t-SNE 降维展示，直观呈现不同声纹的聚类效果。

2.  **分数归一化研究 (Level 6)**
    *   研究并实现 Z-Norm/AS-Norm。
    *   集成到 `voice_engine/infer.py` 和 `backend/api/views/voice.py` 中。

3.  **整理实验报告**
    *   汇总所有图表（ROC/EER, 噪声鲁棒性, 聚类图）到 `reports/archive/`。
    *   更新项目 README，展示核心成果。

4.  **工程化准备 (Transition to Engineering)**
    *   完成深度学习核心实验后，开始着手 Docker 化与 Kubernetes 部署（参考 `docs/upgrade_plans/项目升级规划.md`）。
    *   前端优化：引入 Skills 提升 UI 科技感（Canvas 动态波形图等）。
