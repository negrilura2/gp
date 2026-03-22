# 论文图表与指标生成提交SOP

适用项目：`d:\traepg\gp\voice_access_control`

## 1. 目标

本SOP用于一次性完成以下工作：

1. 检查 `reports/` 是否存在冗余目录；
2. 生成论文可用的核心图表与指标；
3. 将结果整理并提交到 GitHub。

## 2. 最终应产出的内容

建议至少确保以下文件存在：

- `reports/backend_responses/none/roc.png`
- `reports/backend_responses/none/eer_threshold.json`
- `reports/backend_responses/none/det_points.json`
- `reports/backend_responses/none/mindcf.json`
- `reports/backend_responses/none/score_dist.json`
- `reports/backend_responses/none/calibration.json`
- `reports/backend_responses/znorm/*`
- `reports/backend_responses/tnorm/*`
- `reports/backend_responses/snorm/*`
- `reports/plots/embedding/*.png`
- `reports/plots/noise/*.png`
- `reports/strategy/strategy_curves.png`
- `reports/score_norm/summary.json`
- `reports/plots/latency/latency_curve.png`

## 3. 冗余检查与整理

在项目根目录执行：

```powershell
cd d:\traepg\gp\voice_access_control
Get-ChildItem reports -Directory | ForEach-Object {
  $count=(Get-ChildItem $_.FullName -Recurse -File | Measure-Object).Count
  "{0}`tfiles={1}" -f $_.Name,$count
}
```

判定原则：

- `metrics/`、`noise_tests/`、`score_norm/` 为空时，可视为阶段性空目录；
- `score_norm/` 虽可为空，但后续汇总会写入，不建议删除；
- `backend_responses/`、`plots/`、`strategy/` 为有效产物目录，保留。

## 4. 图表与指标生成步骤

### 4.1 生成 ROC/EER/DET/minDCF/校准（四种归一化）

```powershell
cd d:\traepg\gp\voice_access_control
$methods = @("none","znorm","tnorm","snorm")
foreach ($m in $methods) {
  python -m scripts.evaluate --config configs/evaluate.yaml --score_norm $m
}
```

### 4.2 生成嵌入可视化图（t-SNE + PCA）

```powershell
python -m scripts.analysis.plot_embedding --config configs/plot_embedding.yaml --method tsne --score_norm none
python -m scripts.analysis.plot_embedding --config configs/plot_embedding.yaml --method pca  --score_norm none
```

### 4.3 生成噪声鲁棒性图（基础模型 + 噪声增强模型）

```powershell
python -m scripts.analysis.noise_robustness --config configs/noise_robustness.yaml --model_path checkpoints/ecapa_mfcc_delta_best.pth
python -m scripts.analysis.noise_robustness --config configs/noise_robustness.yaml --model_path checkpoints/noise_augmented/ecapa_mfcc_delta_best.pth
```

### 4.4 生成实验汇总（策略曲线 + score_norm汇总）

先生成 `reports/score_norm/*.json`：

```powershell
New-Item -ItemType Directory -Force reports/score_norm | Out-Null
$methods = @("none","znorm","tnorm","snorm")
foreach ($m in $methods) {
  $src = "reports/backend_responses/$m/eer_threshold.json"
  if (Test-Path $src) {
    $j = Get-Content $src -Raw | ConvertFrom-Json
    $out = @{
      method = $m
      eer = $j.eer
      threshold = $j.threshold
      mindcf_res = @{ min_dcf = $j.mindcf }
    } | ConvertTo-Json -Depth 5
    Set-Content -Path "reports/score_norm/$m.json" -Value $out -Encoding UTF8
  }
}
```

再执行汇总脚本：

```powershell
python -m scripts.analysis.summarize_experiments --config configs/summarize_experiments.yaml
```

### 4.5 生成延迟曲线图（用于系统延迟测试）

```powershell
python backend/manage.py shell -c "import os; import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; from api.models import VerifyLog; qs=list(VerifyLog.objects.exclude(latency_ms=0).order_by('timestamp')[:500]); os.makedirs('reports/plots/latency', exist_ok=True); ys=[x.latency_ms for x in qs]; xs=list(range(len(ys))); plt.figure(figsize=(8,4)); plt.plot(xs, ys); plt.xlabel('Sample'); plt.ylabel('Latency (ms)'); plt.title('Verification Latency'); plt.tight_layout(); plt.savefig('reports/plots/latency/latency_curve.png', dpi=160)"
```

## 5. 论文章节与图表对应建议

- 第2章 2.1.2 特征提取：`MFCC 特征图`（可后续补保存版）
- 第5章 5.2.1/5.2.2：`reports/plots/embedding/*.png`
- 第6章 6.3 准确率与噪声：`reports/plots/noise/*.png`
- 第6章 6.3 阈值选取：`reports/backend_responses/*/roc.png` + `eer_threshold.json`
- 第6章 6.3 延迟测试：`reports/plots/latency/latency_curve.png`

## 6. 提交到 GitHub

```powershell
cd d:\traepg\gp\voice_access_control
git status
git add reports docs/论文报告生成与提交SOP.md
git commit -m "docs+reports: generate thesis figures and metrics"
git push
```

## 7. 常见问题

1. `python` 命令不可用  
   先在本机确认可执行解释器路径，再替换命令中的 `python`。

2. CUDA 不可用  
   配置文件中 `device` 可改为 `cpu`，或命令行显式传 `--device cpu`。

3. `feature dimension mismatch`  
   通常是模型与特征类型不一致，检查：
   - 模型：`checkpoints/*.pth` 对应的 `*.json` 元信息；
   - 特征目录：`data/features/mfcc_delta` 与 `data/features/logmel`。

4. `reports/score_norm/summary.json` 未生成  
   先确认 `reports/score_norm/*.json` 已按 4.4 步骤创建。
