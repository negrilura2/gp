# README — Voice Access Control（声纹门禁系统）

> 项目目标：基于声纹识别（ECAPA-TDNN），实现一个软件门禁原型，包含数据预处理、特征提取、模型训练/推理、注册（enroll）与验证（verify）、以及供前端/后端调用的 API（Django）。
> 该 README 针对接手开发者/评审，提供完整的环境、目录说明、运行命令与常见问题排查。

---

## 主要信息（概览）

* 语言 / 框架：Python 3.9.18，PyTorch，Django（REST），Vue.js（前端建议）
* 推荐管理工具：Anaconda（conda 环境），`pip` 安装包依赖
* 模型：轻量 ECAPA-TDNN（实现文件 `model/ecapa_tdnn.py`）
* 模块分布：`model/`（训练/推理/注册等），`scripts/`（预处理、特征提取、演示脚本），`backend/`（Django 后端）

---

# 快速上手（最短路径）

1. 克隆代码／拷贝到 `D:\pythoncode\voice_access_control`（或其他路径）。
2. 创建 conda 环境（推荐）并激活：

```bash
conda create -n voice_access python=3.9.18 -y
conda activate voice_access
```

3. 在项目根安装开发包（使 `import model` 等可用）：

```bash
cd D:\pythoncode\voice_access_control
pip install -e .
```

4. 安装必要的 Python 包（示例）：

```bash
pip install numpy==1.23.5 scipy==1.10.1 librosa==0.10.1 sounddevice==0.4.6 soundfile python_speech_features matplotlib==3.7.2 scikit-learn django djangorestframework pymysql
# PyTorch：根据是否使用 GPU 选择官方或 conda 指令（示例：CPU wheel）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

5. 运行 Django（示例）：

```bash
cd backend
python manage.py migrate
python manage.py runserver
```

---

# 项目结构（重要文件/目录）

```
voice_access_control/
├─ model/                 # 模型相关（训练/推理/注册/验证）
│  ├─ __init__.py
│  ├─ dataset.py
│  ├─ ecapa_tdnn.py
│  ├─ train.py
│  ├─ infer.py
│  ├─ enroll.py
│  └─ verify_demo.py
├─ scripts/               # 数据处理、特征提取、演示脚本
│  ├─ __init__.py
│  ├─ preprocess.py
│  ├─ feature_extraction.py
│  ├─ eval_threshold.py
│  └─ record_and_verify.py
├─ data/
│  ├─ raw/                # 原始录音（按用户子目录）
│  ├─ processed/          # 预处理后 wav
│  ├─ features/           # MFCC npy（按用户）
│  └─ voiceprints/        # 模板文件（user_templates.npy）
├─ models/                # 训练保存的权重（.pth）
├─ reports/               # ROC/EER 等可视化输出
├─ backend/               # Django 项目（api）
└─ setup.py               # 项目包化
```

---

## 已完成（当前状态，接手者可复现）

* 环境准备与包化（`setup.py`），可通过 `pip install -e .` 使用 `import model`。
* 数据处理脚本：`scripts.data.preprocess` 已实现去静音、重采样、预加重、保存到 `data/processed`。
* 特征提取：`scripts.data.feature_extraction` / `extract_mfcc.py` 将每条 wav 提取 MFCC(13)+Δ+Δ² → 39d 并保存 `.npy` 到 `data/features`。
* 轻量 ECAPA-TDNN 实现（`model/ecapa_tdnn.py`）、训练脚本（`model/train.py`）可运行并保存模型（你曾做过 `epoch3` 的训练）。
* 模板生成（infer）及演示验证脚本（`model/infer.py`, `model/verify_demo.py`, `scripts.audio.record_and_verify`）已实现并能完成本地 enroll/verify 流程。
* 阈值评估：`scripts.eval.eval_threshold` 生成 ROC 图与 `reports/eer_threshold.json`（已得到 AUC, EER, suggested threshold）。
* Django 后端骨架与 API（enroll/verify）已搭建并可运行（`backend/`，已处理包导入问题）。
* 训练 / 验证一次性演示已完成（终端输出、ROC 图、模板生成）。

---

## 未完成（必须在毕设交付前完成）

> 这些项直接关系到毕业设计任务书要求或答辩必须交付的要件，优先级高。

1. **论文/文档相关**

   * ☐ 完成完整的毕业设计说明书（规范排版、图表、实验数据、讨论）。
   * ☐ 完成外文翻译（不少于 3000 字）并附英文原文。
   * ☐ 完成开题、中期与最终报告文档（含参考文献不少于任务书要求）。

2. **数据库 & 后端完善**

   * ☐ 完整 MySQL 表与迁移脚本（若已用 sqlite 进行测试，请切换/配置 MySQL 并测试迁移）。
   * ☐ 改进 API 的认证与权限（当前可用但需在 `Enroll`/`Verify` 等操作上完善权限策略）。
   * ☐ 日志体系化（后端文件日志 `logs/`、VerifyLog 表并添加索引与管理界面）。

3. **前端（答辩交互界面）**

   * ☐ 最小 Vue 前端（录音按钮、注册、验证、结果展示、管理员查看日志与 ROC 图），并与后端 API 联调。
   * ☐ 前端部署 / 打包说明（或使用纯 Postman 演示备用）。

4. **实验设计与报告**

   * ☐ 在更多数据 / 增强策略上完成系统训练（完成至少一组对比实验：baseline vs 增强/不同损失）。
   * ☐ 写清楚实验配置（训练集/验证集划分、数据增强策略、超参、硬件环境），并提交训练日志。

5. **论文质量与引用**

   * ☐ 在论文和开题报告里补全并规范 20 篇参考文献（近三年为主，外文不少于 5 篇）。

6. **演示稳定性**

   * ☐ 注册（enroll）流程稳健化：支持 multi-shot（保存多条 embedding 而非仅平均），并支持删除/更新模板操作。
   * ☐ Verify 报错处理、异常情况（空音频、采样率不符、回放攻击等）需要更友好的返回信息。

7. **环境与部署**

   * ☐ Docker 化（Dockerfile + docker-compose），包含 MySQL 与 Django 服务，便于答辩机一键启动。
   * ☐ 部署文档（如何在另一台机器复现整个系统）。

---

## 待优化 / 可选（加分项，建议在论文阶段实现）

1. **反重放 / 反伪造模块**（Anti-spoofing）

   * 集成活体检测（如 MagLive 思路、声纹反欺骗模型或基于传感器的检测），并把其作为 verify 前的前置检查。

2. **Score Normalization（Z-norm/T-norm）**

   * 在 verify 阶段对相似度做归一化以稳定阈值，尤其在跨设备/跨时段场景中有显著帮助。

3. **更强的训练策略**

   * 使用 AAM-Softmax / ArcFace 类别损失以提高 embedding 的判别力；引入数据增强（噪声/混响/变速）与更长训练时间（更多 epochs）。

4. **多模态融合**

   * 人脸 + 声纹融合验证（如 FaceNet + ECAPA 得分融合）以提高安全性（论文加分项）。

5. **导出模型以便移动部署**

   * 导出 TorchScript / ONNX，测试 onnxruntime 推理加速，减少推理延迟。

6. **性能与并发优化**

   * 在后端使用 worker 进程（Gunicorn / Uvicorn）和模型单例加载策略，控制并发和显存/CPU利用。

7. **更完备的监控与可视化**

   * 后端统计面板（使用 ECharts），识别成功率、错误率、按日/用户统计图表。

---

## 运行与验证命令（常用命令清单）

* 数据预处理：

```bash
python -m scripts.preprocess
```

* 特征提取：

```bash
python -m scripts.feature_extraction
```

* 训练模型：

```bash
python -m model.train --feature_dir data/features --save_dir models --epochs 30 --batch_size 32
```

* 生成模板（infer）：

```bash
python -m model.infer --model_path models/ecapa_best.pth --feature_dir data/features
```

* 评估 EER / 生成 ROC：

```bash
python -m scripts.eval_threshold --model models/ecapa_best.pth --feature_dir data/features --out_dir reports --max_pairs 10000
```

* 注册（enroll）：

```bash
python -m model.enroll alice data/enroll/alice/1.wav data/enroll/alice/2.wav data/enroll/alice/3.wav
```

* 本地录音并验证（交互）：

```bash
python -m scripts.record_and_verify verify --threshold 0.70
```

* 启动后端：

```bash
cd backend
python manage.py runserver 0.0.0.0:8000
```

* API 示例（curl）：

```bash
curl -X POST -F "user_id=alice" -F "files=@/path/1.wav" http://127.0.0.1:8000/api/enroll/
curl -X POST -F "file=@/path/test.wav" -F "threshold=0.70" http://127.0.0.1:8000/api/verify/
```

---

## 数据与实验复现（说明）

* `scripts/eval_threshold.py` 抽样计算同/异对分数并绘制 ROC，保存 `reports/roc.png` 与 `reports/eer_threshold.json`；该 EER 是在当前 feature 集统计下的平衡点，仅用于学术评估（论文部分）。
* 演示时可选择比 EER 更严格的阈值（如 0.7–0.75）以降低现场误放概率（我们已在项目中预置 `--threshold` 参数）。
* 请在实验报告中注明数据划分（train/valid/test）、增强策略、batch size、epoch、学习率 schedule 与硬件（GPU/CPU）信息。

---

## 部署建议（生产级注意）

* 不要在生产用 `DEBUG=True`，使用环境变量管理机密信息（DB 密码、SECRET_KEY）。
* 在服务端把模型单例加载到 worker 进程，避免每次请求重复加载。
* 推荐使用 Gunicorn + Nginx 或 Uvicorn + Nginx；在容器中运行请编写 Dockerfile 与 docker-compose。
* 生产上建议把模型部署在 GPU 节点或使用 inference server（若需低延迟）。

---

## 毕设交付清单（对照任务书要求）

* 开题报告（含参考文献）
* 中期报告
* 外文翻译与原文（≥3000 字）
* 源代码与模型（models/*.pth）
* 系统演示（后端 API + 最小前端或 curl 脚本）
* 毕业设计说明书（规范格式）
* 报告中的实验数据（ROC/EER/训练曲线/超参细节）
* 答辩 PPT 与现场演示脚本（包括操作步骤与应急方案）

---

## 常见问题与排查（快速）

* `ModuleNotFoundError: No module named 'model'`

  * 解决：在项目根执行 `pip install -e .`（或确保 PYTHONPATH 包含项目根）。
* `ImportError: numpy.core.multiarray failed to import` / DLL 问题

  * 解决：用 conda 安装 numpy、scipy（推荐），或重建 conda env。
* `sounddevice` 无法录音 / 权限问题

  * 检查 `sd.query_devices()`、系统麦克风权限、Windows 的隐私设置。
* Django 启动加载模型慢或 OOM

  * 把模型加载放到 worker 进程启动阶段（非 request 时），限制并发 worker 数量。

---

## 如何接手（交接说明）

1. 克隆仓库并在项目根运行 `pip install -e .`。
2. 按上面“快速上手”安装依赖并运行数据库迁移（`python manage.py migrate`）。
3. 先用 `scripts/preprocess.py` + `scripts/feature_extraction.py` 处理一小批数据并用 `model/train.py` 做一次快速训练（如 3 个 epoch）验证流程完整性。
4. 运行 `python -m scripts.eval_threshold` 生成 ROC/EER；运行 `python -m model.enroll` + `python -m scripts.record_and_verify verify` 做一次 end-to-end 验证。
5. 在开始修改代码前，先在 `README.md` 中记录实施步骤与环境（确保后续复现）。

---

