# 毕设项目：声纹门禁系统 — 任务清单

## Phase 1：Bug 修复 & 后端稳定化 ✅

- [x] 补全 `requirements.txt`
- [x] 修复模板路径不一致 bug（`enroll.py` vs `verify_demo.py`）
- [x] 实现模型单例加载（`backend/api/model_loader.py`）
- [x] 用户注册/登录 API + Token 认证
- [x] EnrollView 需认证；VerifyView 可匿名
- [x] 文件上传校验（格式、大小）
- [x] 结构化日志（Django LOGGING → `logs/`）
- [x] `VerifyLog` 增加 `client_ip`；新增 `EnrollLog`
- [x] 新增路由：`register/`、`login/`、`logs/`、`stats/`、`users/`
- [x] Django check & migrate 通过
分析了一下依赖关系：

Phase 2 不影响 Phase 3。原因：

Multi-shot enroll 只改后端 
enroll.py
 的存储逻辑，API 接口 (POST /api/enroll/ with files) 不变
verify_demo.py
 在 Phase 1 已经提前写好了 multi-shot 兼容逻辑（单条和多条 embedding 都能处理）
训练改进（LR scheduler / AAM-Softmax）是离线脚本，跟前端完全无关
所以 先做 Phase 3（Vue.js 前端），这样能尽早看到完整系统的交互效果。Phase 2 随时可以无缝补上。

## Phase 2：核心功能增强

- [ ] Multi-shot enroll（保留多条 embedding）
- [ ] Verify 取多模板最大相似度
- [ ] Verify 异常处理（空音频、采样率、格式）
- [ ] 训练脚本加 LR scheduler + 训练曲线保存
- [ ] 可选 AAM-Softmax loss

## Phase 3：Vue.js + Element Plus 前端 [IN PROGRESS]

- [ ] 创建 Vue 3 项目
- [ ] 登录/注册页
- [ ] 声纹注册页（录音 × 3 → 上传）
- [ ] 声纹验证页（录音 → 结果动画展示）
- [ ] 个人中心（验证历史）
- [ ] 管理后台（用户管理、日志、ROC 图、ECharts 统计）

## Phase 4：Docker 化

- [ ] Dockerfile + docker-compose.yml
- [ ] 部署文档

## Phase 5：MySQL 切换 & 实验

- [ ] `settings.py` 切 MySQL + 迁移
- [ ] 对比实验 + 论文图表生成