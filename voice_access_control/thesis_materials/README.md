# 论文材料汇总

本文件夹用于集中整理当前项目可直接用于论文写作与答辩准备的材料。

## 目录说明

- `01_outline_and_docs/`：论文大纲、项目 README、图表生成 SOP
- `02_figures_existing/`：当前项目中已经存在的图表与原始指标
- `03_code_sources/`：适合第 5 章系统实现引用的核心代码来源
- `04_generated_guides/`：章节材料对照表、代码片段摘录、后续生成脚本
- `05_missing_items/`：当前缺失但建议补齐的论文材料清单

## 当前可直接用于论文的图表

### 第5章 系统实现

- 嵌入可视化图：
  - `02_figures_existing/chapter5_embedding/tsne_mfcc_delta_none_ecapa_mfcc_delta_best.png`
  - `02_figures_existing/chapter5_embedding/pca_mfcc_delta_none_ecapa_mfcc_delta_best.png`

### 第6章 系统测试

- 噪声鲁棒性图：
  - `02_figures_existing/chapter6_noise/noise_robustness_mfcc_delta_noise_ecapa_mfcc_delta_best.png`
  - `02_figures_existing/chapter6_noise/noise_robustness_mfcc_delta_white_ecapa_mfcc_delta_best.png`
- 训练策略对比图：
  - `02_figures_existing/chapter6_strategy/strategy_curves.png`
- 归一化结果原始指标：
  - `02_figures_existing/raw_metrics/none.json`
  - `02_figures_existing/raw_metrics/znorm.json`
  - `02_figures_existing/raw_metrics/tnorm.json`
  - `02_figures_existing/raw_metrics/snorm.json`

## 当前检查结论

- 已有材料能够覆盖大纲中的嵌入可视化、噪声鲁棒性、训练策略对比、部分 score normalization 指标
- 当前缺失或未在 `reports/` 中找到的关键论文材料包括：
  - ROC 曲线图与 `backend_responses/*` 全套评估结果
  - DET、minDCF、分数分布、校准结果
  - 延迟曲线图
  - 可直接插入论文的 MFCC 特征图
  - 前端页面与后台页面截图

## 推荐先看

- `04_generated_guides/章节材料对照表.md`
- `04_generated_guides/关键代码片段摘录.md`
- `04_generated_guides/缺失图表生成命令.md`
- `05_missing_items/缺失论文材料清单.md`
