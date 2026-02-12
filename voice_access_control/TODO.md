## TODO.md — 未完成项 & 优先级（复制到项目根的 TODO.md）

下面 TODO 按优先级、所需文件修改、命令与验收标准列出，便于接手开发者逐项完成并打勾。

### 一、必须完成（交付前，最高优先级）

- [ ] **毕业设计说明书（paper）**
  - 内容：需求、设计、实现、实验（数据与图表）、讨论、结论、参考文献。
  - 相关文件：`docs/thesis.docx`（或 `docs/thesis.md`）。
  - 预计工作量：7–10 天（含图表与定稿）。
  - 验收：包含 ROC/EER 图、实验表格、代码链接与模型版本号。

- [ ] **外文翻译（≥3000 字）**
  - 相关文件：`docs/foreign_paper.txt` + `docs/translation.md`。
  - 验收：英文原文 + 中文译文均存在，翻译质量需能对应技术术语。

- [ ] **数据库切换到 MySQL 并测试迁移**
  - 修改：`backend/settings.py` 数据库配置；添加 `env` 读取（示例 `.env.example`）。
  - 命令:
    ```
    python manage.py makemigrations
    python manage.py migrate
    ```
  - 验收：迁移成功，`VoiceTemplate` 与 `VerifyLog` 表结构正确；能通过 admin 查看数据。

- [ ] **API 权限与认证完善**
  - 修改：`backend/api/views.py` 添加权限类（Token 或 Session）。
  - 验收：非登录用户无法调用 enroll 接口（可用 curl 验证返回 403）。

- [ ] **日志体系化**
  - 内容：文件日志（`logs/access.log`）、DB `VerifyLog` 完整字段与索引。
  - 验收：每次 verify/enroll 都产生日志；`logs/` 可按天轮转（或示例脚本）。

- [ ] **前端最小 Demo（必备交互）**
  - 功能：录音 → 上传 enroll；录音 → Upload verify；显示返回结果与 score；管理员查看 logs/ROC。
  - 技术栈：Vue.js + Element Plus（项目建议，但可先用静态 HTML + fetch 实现）。
  - 验收：在本地用浏览器操作完整流程并截图作为演示材料。

- [ ] **多条模板支持（multi-shot enroll）**
  - 修改：`model/enroll.py` 保存多条 embedding 到 `data/voiceprints/{user}.npy` 或改存字典结构。
  - Verify 改为在多模板中取最大相似度.
  - 验收：对同用户不同 utterance 验证稳定性提升（记录对比数据）。

- [ ] **部署文档与 Docker 化**
  - 文件：`Dockerfile`, `docker-compose.yml`, `deploy/README.md`。
  - 验收：能够在干净环境用 `docker-compose up` 启动后端与 MySQL，并能访问 API.

### 二、短期优化（答辩加分，优先级中）

- [ ] **跨设备/噪声评估套件**
  - 脚本：`scripts/cross_device_test.py`（批量播放/回放评估）。
  - 验收：报告包含同设备/回放/噪声条件下 score 分布表。

- [ ] **Z-norm/T-norm 模块（可配置）**
  - 修改：`model/verify_demo.py` 增加 `--znorm` 参数并提供计算样例。
  - 验收：启用后阈值在跨设备场景下更稳定（至少记录对比结果）。

- [ ] **简单 Anti-Replay（heuristic）**
  - 方法：能检测出扬声器回放的能量谱/相位异常或基于 MagLive 的启示实现简化版。
  - 验收：对一组回放样本检测率提高（给出 TP/FP 统计）。

- [ ] **导出模型（TorchScript / ONNX）**
  - 脚本：`model/export_onnx.py`。
  - 验收：使用 onnxruntime 能在 CPU 环境加载并得到与 PyTorch 接近的输出。

### 三、中期/论文级（可选加分）

- [ ] **AAM-Softmax / ArcFace 损失训练对比**
  - 修改：`model/train.py` 支持可替换损失函数配置。
  - 验收：提供对比表格（AUC / EER /训练曲线）。

- [ ] **多模态融合 PoC（人脸+声纹）**
  - 任务：实现人脸特征提取（FaceNet）并做得分融合。
  - 验收：展示融合后在同数据集上的 EER 改善（若有）。

- [ ] **监控与可视化后台**
  - 实现：在 Django 后台提供 ECharts 数据接口并展示 ROC/日活/识别率。
  - 验收：管理员能在浏览器实时看到统计图。

### 四、任务分解与预计工时（示例计划，接手者可调整）
- 环境与 DB 切换（1–2 天）
- API 权限、日志、模型单例加载（2–3 天）
- 多模板 enroll 与 verify 改造（1–2 天）
- 前端最小 demo（2–3 天）
- 文档（README / 论文草稿）与 Docker （2–4 天）

### 五、验收标准（每项必须包含）
1. 命令行与 API 调用完整能复现 end-to-end（raw→processed→feature→train→infer→enroll→verify）。
2. 所有关键脚本带 usage/help（`-h` 输出）并在 README 中有示例命令。
3. 数据/模型/报告路径固定在项目下（避免硬编码外部路径）。
4. 提交时包含：`models/`、`reports/`、`data/voiceprints/`、`backend/migrations/`.

---
