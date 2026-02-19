# 代码库审查与重构规划

## 1. 现状审查：关键“屎山”与技术债

经过代码走查，目前项目在工程规范性上存在显著的“补丁式开发”痕迹，主要集中在以下几个方面。这些问题若不解决，后续引入 Score Normalization 或更换模型时将引发严重回归。

### 1.1 特征提取逻辑严重冗余 (DRY 原则破坏)
目前 **MFCC/LogMel/Delta** 的提取逻辑散落在至少 **4** 个独立文件中，且实现细节不一致（这也是导致 Clean/Noise 准确率对不齐的根本原因）。

| 模块/脚本 | 文件路径 | 问题描述 |
| :--- | :--- | :--- |
| **训练数据预处理** | `scripts/data/feature_extraction.py` | 使用 `python_speech_features`。无预加重，无归一化。 |
| **注册/验证引擎** | `voice_engine/enroll.py` | 重新实现了一套逻辑。包含 `pre_emphasis` 和 `normalize`（部分被注释）。逻辑混乱。 |
| **噪声测试** | `scripts/eval/noise_robustness.py` | 第三套实现。近期打补丁加入了 `scipy.signal.resample` 替换 `librosa`，并手动回滚了 LogMel 逻辑以对齐训练。 |
| **Django 后端** | `backend/api/model_loader.py` | 硬编码了特征类型推断逻辑，与引擎层逻辑重复。 |

**风险**: 修改一个特征参数（如 `n_mels`），需要同时修改 4 个文件，极易漏改。

### 1.2 配置硬编码 (Magic Numbers)
- `SAMPLE_RATE = 16000` 散落在所有脚本头部。
- `n_mels=40` 经常作为默认参数，但缺乏统一配置源。
- 路径（如 `data/features`, `models/ecapa_best.pth`）在脚本中随处可见，一旦目录结构变更（如刚才的重构），大量脚本失效。

### 1.3 模型加载与推断脆弱
- **类型推断**: 依靠文件名（`mfcc`, `logmel`）或权重维度（`39`, `40`）来猜测模型类型。如果训练了一个 `n_mels=80` 的模型，系统会误判。
- **单例模式**: Django 的 `model_loader.py` 和 `voice_engine/enroll.py` 中的 `load_model` 逻辑重复。

---

## 2. 下一步规划：重构路线图 (Refactoring Roadmap)

为了支持后续的 **Deep Learning Upgrade (Level 5 & 6)**，我们必须先清理地基。

### ✅ 阶段一：配置与核心引擎统一 (立即执行)
目标：消灭重复代码，建立统一的 `voice_engine` 调用入口。

1.  **建立配置中心 (`voice_engine/config.py`)**
    *   定义全局常量：`SAMPLE_RATE`, `N_MELS`, `N_MFCC`, `WINDOW_SIZE`, `HOP_LENGTH`。
    *   定义默认路径。

2.  **提取特征引擎 (`voice_engine/features.py`)**
    *   创建一个 `FeatureExtractor` 类或纯函数模块。
    *   **统一逻辑**: Load Audio -> Resample (Scipy) -> Pre-emphasis -> Normalize (Optional) -> Extract (Python_Speech_Features) -> Transpose。
    *   **所有** 脚本（训练、测试、注册）必须调用此模块，严禁私自实现提取逻辑。

3.  **重构调用方**
    *   修改 `enroll.py`, `verify_demo.py`, `noise_robustness.py`, `train.py` 使用新的 `features.py`。
    *   **Refactoring**: `verify_demo.py` -> `verify.py` (cleaner name).

### 阶段二：模型封装与元数据 (Metadata)
目标：让模型“自描述”，不再靠猜。

1.  **模型元数据 (`model_config.json`)**
    *   训练保存模型时，同步保存一个 `.json` 文件，记录：`feature_type`, `n_mels`, `embedding_dim`, `train_date` 等。
2.  **统一模型加载器 (`voice_engine/core.py`)**
    *   创建一个 `VoiceModel` 类，封装 `LightECAPA`。
    *   `VoiceModel.load(path)` 自动读取配套 JSON，初始化正确的预处理管线。

### 阶段三：可视化与高级评估 (Deep Learning Upgrade)
在重构完成后，执行以下任务将变得非常简单：

1.  **Embedding 可视化**: 直接调用 `VoiceModel.embed(wav_path)` 获取向量，不再关心预处理细节。
2.  **Score Normalization**: 在 `VoiceModel.verify()` 方法中集成 Z-Norm/S-Norm 策略。

---

## 3. 执行建议

**我们现在的首要任务是执行“阶段一”**。这能立刻解决您提到的“三个特征补丁式修改”的痛点。

是否立即开始 **阶段一：创建 `voice_engine/config.py` 和 `voice_engine/features.py`**？
