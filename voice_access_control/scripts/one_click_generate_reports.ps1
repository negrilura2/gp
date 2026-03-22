param(
    [string]$PythonExe = "python",
    [string]$CondaEnvName = "voice_access",
    [switch]$SkipLatency,
    [switch]$DryRun,
    [switch]$SkipDependencyCheck
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Resolve-PythonPath {
    param(
        [string]$Requested,
        [string]$EnvName
    )
    if ($Requested -ne "python") {
        return $Requested
    }
    if ($env:CONDA_PREFIX) {
        $condaPython = Join-Path $env:CONDA_PREFIX "python.exe"
        if (Test-Path $condaPython) {
            return $condaPython
        }
    }
    if ($env:VIRTUAL_ENV) {
        $venvPython = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
        if (Test-Path $venvPython) {
            return $venvPython
        }
    }
    if ($EnvName) {
        $candidates = @()
        if ($env:CONDA_EXE) {
            $condaBase = Split-Path -Parent $env:CONDA_EXE
            $condaRoot = Split-Path -Parent $condaBase
            $candidates += (Join-Path $condaRoot "envs\$EnvName\python.exe")
        }
        $candidates += @(
            "D:\anaconda\envs\$EnvName\python.exe",
            "C:\ProgramData\Anaconda3\envs\$EnvName\python.exe",
            "$env:USERPROFILE\anaconda3\envs\$EnvName\python.exe",
            "$env:USERPROFILE\miniconda3\envs\$EnvName\python.exe"
        )
        foreach ($py in $candidates) {
            if ($py -and (Test-Path $py)) {
                return $py
            }
        }
    }
    $cmd = Get-Command $Requested -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    return $Requested
}

function Resolve-CondaPath {
    $condaCmd = Get-Command "conda" -ErrorAction SilentlyContinue
    if ($condaCmd) {
        return $condaCmd.Source
    }
    if ($env:CONDA_EXE -and (Test-Path $env:CONDA_EXE)) {
        return $env:CONDA_EXE
    }
    return $null
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    $cmdPreview = "$FilePath " + ($Arguments -join " ")
    Write-Host ">> $cmdPreview" -ForegroundColor Cyan
    if ($DryRun) { return }
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $cmdPreview"
    }
}

function Invoke-PythonModule {
    param(
        [Parameter(Mandatory = $true)][string]$Module,
        [Parameter(Mandatory = $false)][string[]]$ModuleArgs = @()
    )
    if ($UseCondaRun) {
        $allArgs = @("run", "-n", $CondaEnvName, "python", "-m", $Module) + $ModuleArgs
        Invoke-Checked -FilePath $ResolvedCondaExe -Arguments $allArgs
    }
    else {
        $allArgs = @("-m", $Module) + $ModuleArgs
        Invoke-Checked -FilePath $ResolvedPythonExe -Arguments $allArgs
    }
}

function Test-PythonModule {
    param([string]$ModuleName)
    if ($DryRun) { return $true }
    if ($UseCondaRun) {
        & $ResolvedCondaExe "run" "-n" $CondaEnvName "python" "-c" "import $ModuleName"
    }
    else {
        & $ResolvedPythonExe "-c" "import $ModuleName"
    }
    return ($LASTEXITCODE -eq 0)
}

$ResolvedPythonExe = Resolve-PythonPath -Requested $PythonExe -EnvName $CondaEnvName
$ResolvedCondaExe = Resolve-CondaPath
$UseCondaRun = $false
if ($CondaEnvName -and $ResolvedCondaExe) {
    $UseCondaRun = $true
}

Write-Host "Project root: $ProjectRoot" -ForegroundColor Green
Write-Host "Python executable: $ResolvedPythonExe" -ForegroundColor Green
Write-Host "Conda env hint: $CondaEnvName" -ForegroundColor Green
if ($UseCondaRun) {
    Write-Host "Execution mode: conda run (-n $CondaEnvName)" -ForegroundColor Green
}
else {
    Write-Host "Execution mode: direct python" -ForegroundColor Green
}
if ($DryRun) {
    Write-Host "DryRun mode enabled. Commands will not be executed." -ForegroundColor Yellow
}

if (-not $SkipDependencyCheck) {
    $requiredModules = @("torch", "numpy", "sklearn", "matplotlib", "yaml", "django", "soundfile", "scipy")
    $missing = @()
    foreach ($m in $requiredModules) {
        if (-not (Test-PythonModule -ModuleName $m)) {
            $missing += $m
        }
    }
    if ($missing.Count -gt 0) {
        $installLine = "$ResolvedPythonExe -m pip install " + ($missing -join " ")
        throw "Python依赖缺失: $($missing -join ', ')`n请先安装后重试：`n$installLine"
    }
}

$normMethods = @("none", "znorm", "tnorm", "snorm")

foreach ($m in $normMethods) {
    Invoke-PythonModule -Module "scripts.evaluate" -ModuleArgs @("--config", "configs/evaluate.yaml", "--score_norm", $m)
}

Invoke-PythonModule -Module "scripts.analysis.plot_embedding" -ModuleArgs @("--config", "configs/plot_embedding.yaml", "--method", "tsne", "--score_norm", "none")
Invoke-PythonModule -Module "scripts.analysis.plot_embedding" -ModuleArgs @("--config", "configs/plot_embedding.yaml", "--method", "pca", "--score_norm", "none")

$modelA = "checkpoints/ecapa_mfcc_delta_best.pth"
$modelB = "checkpoints/noise_augmented/ecapa_mfcc_delta_best.pth"
if (Test-Path $modelA) {
    Invoke-PythonModule -Module "scripts.analysis.noise_robustness" -ModuleArgs @("--config", "configs/noise_robustness.yaml", "--model_path", $modelA)
}
if (Test-Path $modelB) {
    Invoke-PythonModule -Module "scripts.analysis.noise_robustness" -ModuleArgs @("--config", "configs/noise_robustness.yaml", "--model_path", $modelB)
}

if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path "reports/score_norm" | Out-Null
    foreach ($m in $normMethods) {
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
}
else {
    Write-Host ">> build reports/score_norm/*.json" -ForegroundColor Cyan
}

Invoke-PythonModule -Module "scripts.analysis.summarize_experiments" -ModuleArgs @("--config", "configs/summarize_experiments.yaml")

if (-not $SkipLatency) {
    $latencyPy = @'
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from api.models import VerifyLog
qs = list(VerifyLog.objects.exclude(latency_ms=0).order_by("timestamp")[:500])
os.makedirs("reports/plots/latency", exist_ok=True)
ys = [x.latency_ms for x in qs]
xs = list(range(len(ys)))
plt.figure(figsize=(8, 4))
plt.plot(xs, ys)
plt.xlabel("Sample")
plt.ylabel("Latency (ms)")
plt.title("Verification Latency")
plt.tight_layout()
plt.savefig("reports/plots/latency/latency_curve.png", dpi=160)
'@
    $latencyPyPath = Join-Path $ProjectRoot "scripts\temp_plot_latency.py"
    $latencyPy | Set-Content -Path $latencyPyPath -Encoding UTF8

    if ($UseCondaRun) {
        $fullCmd = "& `"$ResolvedCondaExe`" run --no-capture-output -n $CondaEnvName python backend/manage.py shell"
        Write-Host ">> $fullCmd < $latencyPyPath" -ForegroundColor Cyan
        if (-not $DryRun) {
            # Use cmd.exe to handle the stdin redirection properly
            cmd.exe /c "`"$ResolvedCondaExe`" run --no-capture-output -n $CondaEnvName python backend/manage.py shell < `"$latencyPyPath`""
            if ($LASTEXITCODE -ne 0) { throw "Command failed: latency plot" }
        }
    }
    else {
        $fullCmd = "& `"$ResolvedPythonExe`" backend/manage.py shell"
        Write-Host ">> $fullCmd < $latencyPyPath" -ForegroundColor Cyan
        if (-not $DryRun) {
            cmd.exe /c "`"$ResolvedPythonExe`" backend/manage.py shell < `"$latencyPyPath`""
            if ($LASTEXITCODE -ne 0) { throw "Command failed: latency plot" }
        }
    }
    
    if (Test-Path $latencyPyPath) {
        Remove-Item $latencyPyPath -Force
    }
}

$expected = @(
    "reports/backend_responses/none/roc.png",
    "reports/backend_responses/none/eer_threshold.json",
    "reports/backend_responses/znorm/roc.png",
    "reports/backend_responses/tnorm/roc.png",
    "reports/backend_responses/snorm/roc.png",
    "reports/plots/embedding",
    "reports/plots/noise",
    "reports/strategy/strategy_curves.png",
    "reports/score_norm/summary.json",
    "reports/plots/latency/latency_curve.png"
)

Write-Host "`nArtifacts check:" -ForegroundColor Green
foreach ($p in $expected) {
    if (Test-Path $p) {
        Write-Host "[OK] $p" -ForegroundColor Green
    }
    else {
        Write-Host "[MISSING] $p" -ForegroundColor Yellow
    }
}

Write-Host "`nDone."
