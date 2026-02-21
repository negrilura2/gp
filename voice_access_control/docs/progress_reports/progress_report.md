# 项目进展报告 (2026-02-19)

## 📅 核心进展摘要
本日工作主要围绕 **Level 3 噪声鲁棒性实验** 的攻坚、代码库的 **架构重构** 以及 **Level 4 训练策略** 的实施展开。成功解决了 Windows 环境下的依赖冲突问题，并完成了从扁平化脚本向模块化工程的初步转型。

---

## 🛠️ 1. 深度学习实验与优化 (Deep Learning)

### 1.1 Level 3: 噪声鲁棒性实验 (Noise Robustness)
*   **状态**: ✅ 已完成 (LogMel, MFCC_Delta)
*   **问题**: `noise_robustness.py` 在 Windows 下因 `librosa` 与 `pkg_resources` 交互及多进程问题导致频繁卡死 (Hang)。
*   **解决方案**:
    1.  **库替换**: 将 `librosa.resample` 替换为 `scipy.signal.resample`，移除对 `librosa` 重型依赖的调用。
    2.  **特征提取重构**: 引入 `torchaudio` 替代 `librosa.feature.melspectrogram`，彻底解决了 Windows 下的死锁问题，并提升了提取速度。
    3.  **内存优化**: 增加了 CUDA OOM (Out Of Memory) 捕获机制，当显存不足时自动降级到 CPU 或减小 Batch Size。
    4.  **逻辑对齐**: 修正了噪声测试中的特征提取逻辑（移除了非标准的归一化步骤），确保与训练阶段 (`train.py`) 的预处理完全一致。
*   **产出**: 
    *   生成的鲁棒性曲线图已归档至 `reports/archive/plots/noise/`。
    *   测试数据 JSON 归档至 `reports/archive/noise_tests/`。

### 1.2 Level 4: 训练策略实验 (Training Strategy)
*   **状态**: 🔄 进行中 (代码已就绪，正在进行对比实验)
*   **实施**: 
    *   修改 `voice_engine/train.py`，新增 `--early_stop` 和 `--patience` 参数。
    *   **EER 计算优化**: 引入 `--eer_interval` 参数，允许用户配置 EER 评估频率（默认 5 epochs），解决评估过慢问题。
    *   **Early Stopping 逻辑升级**: 将早停判断逻辑与 EER 评估挂钩，仅在计算了 EER 的 Epoch 更新 Patience 计数，避免在不计算 EER 的 Epoch 误触发早停。
    *   **Windows 性能优化**: 针对 Windows 平台 DataLoader 多进程启动慢的问题，自动检测并强制使用单线程 (`num_workers=0`)，将训练速度从 ~20s/epoch 提升至 ~2s/epoch。
*   **验证**:
    *   解决了 EER 显示为 0.0000 的问题（改为 "N/A"）。
    *   修复了 dataset 加载路径在 Windows 下的健壮性问题。

---

## 🏗️ 2. 系统架构重构 (Refactoring)

### 2.1 目录结构优化
为解决项目根目录文件杂乱的问题，建立了标准化的归档机制：
*   **Reports**: `reports/` -> `reports/archive/{plots, metrics, noise_tests, backend_responses}`
*   **Models**: `models/` -> `models/archive/{feature_type}/`
*   **适配**: 全面更新了 `train.py`, `eval_threshold.py`, `noise_robustness.py` 以及后端代码，确保文件自动输出到正确分类目录。

### 2.2 Backend API 重构
对 `backend/api` 进行了模块化拆分，提升可维护性：
*   **Views 拆分**: 将扁平的 `views_*.py` 文件迁移至 `backend/api/views/` 包中（如 `auth.py`, `voice.py`）。
*   **统一入口**: 创建 `backend/api/views/__init__.py` 统一导出视图类。
*   **路径修复**: 修复了 `urls.py` 及各模块间的导入路径。

### 2.3 工程化规范
*   **Gitignore**: 更新 `.gitignore`，忽略模型权重文件 (`*.pth`, `*.onnx`)，避免仓库臃肿。

---

## 📝 3. 战略规划 (Strategic Planning)

确立了 **"深度学习优先 -> 工程化跟进"** 的升级路线，并更新了相关文档：

### 3.1 深度学习升级 (`docs/deep_learning_upgrade_plan.md`)
*   确认 Level 3 完成。
*   锁定下一阶段核心为 **Level 5 (可视化)** 和 **Level 6 (分数归一化)**。

### 3.2 工程化与前端优化 (`docs/upgrade_plans/工程化与前端优化规划.md`)
*   **Docker 化**: 规划了 Backend、AI Service、DB 的容器化路径。
*   **解耦**: 计划引入 Kafka/Redpanda 解决推理阻塞问题。
*   **前端**: 规划了引入 Skills (Canvas/WebAudio) 打造科技感 UI 的任务。

---

## 🧾 补充更新 (2026-02-21)

### 已完成与修复
*   **噪声测试路径兼容**: `noise_robustness.py` 自动识别 `data/features/<feature_type>`，修复 `feature_dir 内没有可用特征文件`。
*   **模板构建解包异常**: 兼容 `build_templates` 返回值变化，修复 `ValueError: too many values to unpack`。
*   **结果覆盖问题**: 噪声测试输出文件名加入模型名，避免干净模型与噪声训练模型互相覆盖。
*   **输出目录简化**: 噪声测试结果默认输出至 `reports/noise_tests` 和 `reports/plots/noise`，训练指标默认输出至 `reports/metrics`。
*   **后端读取兼容**: ROC 指标读取支持 `reports/backend_responses` 与历史 `reports/archive/backend_responses` 双路径。

## 🚀 下一步行动 (Next Steps)

1.  **执行 Level 4 对比实验**: 运行 Baseline vs Early Stopping 训练，收集数据。
2.  **实施 Level 5 可视化**: 开发 `plot_embedding.py`，生成 t-SNE 聚类图。
3.  **实施 Level 6 归一化**: 研究并集成 Z-Norm/S-Norm 到推理流程。
