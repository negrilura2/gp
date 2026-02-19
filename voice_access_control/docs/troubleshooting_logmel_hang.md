# 🐛 故障排查记录：LogMel 注册与噪声测试脚本卡死问题

## 问题描述
在 Windows 环境下运行声纹识别系统时，遇到以下两个严重阻塞性问题：

1.  **噪声测试脚本卡死**：
    执行 `scripts.eval.noise_robustness` 评估 LogMel 模型时，脚本在打印出 `pkg_resources` 的 DeprecationWarning 后停止响应（Hang），无任何报错输出，CPU 占用率极低。

2.  **LogMel 模型注册失败**：
    在 Django 后台上传音频注册 LogMel 模型时，请求长时间无响应或最终超时，后台日志无报错，表现为进程死锁。

## 根本原因分析
经过详细调试（添加 DEBUG 日志定位），发现问题出在 `librosa` 库的内部依赖机制上：

1.  **`pkg_resources` 死锁**：
    `librosa` 在加载内部数据（如 Mel 滤波器组）或调用 `resample` 时，会触发 `pkg_resources` (via `lazy_loader`)。在特定的 Windows 环境下（尤其是 Anaconda 环境），这会导致进程死锁（Deadlock）或无限挂起。
    
2.  **错误掩盖**：
    由于死锁发生在 C 扩展或底层资源加载阶段，Python 解释器无法抛出异常，导致 `try-except` 块无法捕获，且最后一条日志往往是 `pkg_resources` 的警告，误导了排查方向。

## 解决方案
为了彻底解决此问题，我们采取了 **“去 librosa 化”** 的策略，将关键路径上的音频处理逻辑替换为更稳定、更高效的替代品。

### 1. 音频重采样 (Resampling)
- **原实现**：`librosa.resample` (依赖 `soxr` 或 `resampy`，易受环境影响)
- **新实现**：`scipy.signal.resample`
- **优势**：`scipy` 是标准科学计算库，稳定性极高，且在 Windows 上无额外的复杂依赖。

### 2. LogMel 特征提取
- **原实现**：`librosa.feature.melspectrogram`
- **新实现**：`torchaudio.transforms.MelSpectrogram`
- **关键点**：为了保证模型输入特征的一致性（不影响已训练好的模型），我们手动对齐了 `torchaudio` 的参数：
    - `norm='slaney'` (匹配 librosa 默认)
    - `mel_scale='slaney'` (匹配 librosa 默认)
    - `power=2.0`
    - 手动实现 `power_to_db` 逻辑：`10 * log10(S / ref_max)`

## 代码变更清单

### `model/enroll.py`
- 引入 `scipy.signal` 和 `torchaudio`。
- 重写 `wav_to_feat_tensor` 函数，增加 `try-except` 捕获所有潜在错误。
- 替换 LogMel 提取逻辑为 `torchaudio` 实现。

### `scripts/eval/noise_robustness.py`
- 引入 `scipy.signal` 和 `torchaudio`。
- 重写 `evaluate_noise` 中的预处理逻辑。
- 增加详细的 `DEBUG` 日志，确保每一步进度可见。

## 验证结果
1.  **噪声测试**：脚本现在可以顺利加载 LogMel 模型，完成 LogMel 特征提取，并输出评估结果（JSON/PNG）。
2.  **后台注册**：Django 后台不再卡死，LogMel 模型可以正常完成声纹注册。

## 经验总结 (Lessons Learned)
1.  **Windows 下的音频库陷阱**：在 Windows 上部署 Python 音频应用时，`librosa` 的某些版本可能会出现兼容性问题，`torchaudio` 通常是更稳健的选择（特别是配合 PyTorch 使用时）。
2.  **依赖隔离**：对于生产级环境，尽量减少对复杂第三方库（如 `librosa`）的运行时依赖，转而使用更轻量或更底层的库（`scipy`, `torchaudio`）。
3.  **日志的重要性**：在遇到“无报错卡死”的情况时，不要盲目猜测，第一时间在关键路径上打满 `DEBUG` 日志，逐步逼近卡死点。
