# Swap the CPU-only PyTorch install in the dev venv for a CUDA build.
#
# Run AFTER setup.sh / a fresh `pip install -r requirements.txt` if you have
# an NVIDIA GPU and want GPU acceleration.  Detects nvidia-smi and the
# installed CUDA toolkit major version, picks the matching PyTorch wheel
# index, then reinstalls torch into the project venv.
#
# Usage (from the repo root):
#   .\scripts\enable-cuda.ps1
#
# Optional override:
#   .\scripts\enable-cuda.ps1 -CudaVersion cu124
#
# Limitations: this targets the dev venv at backend/venv only.  The
# PyInstaller-frozen Windows installer ships CPU torch; CUDA inside the
# bundle is a planned follow-up — see windows/README.md.

param(
    [string]$CudaVersion = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot "backend\venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Could not find $venvPython. Run the backend setup steps first."
    exit 1
}

# 1. Detect NVIDIA driver / CUDA
try {
    $smi = & nvidia-smi 2>$null
    if ($LASTEXITCODE -ne 0) { throw "nvidia-smi exited $LASTEXITCODE" }
} catch {
    Write-Host "No NVIDIA GPU detected (nvidia-smi unavailable)."
    Write-Host "Staying on CPU PyTorch."
    exit 0
}

if (-not $CudaVersion) {
    # Parse "CUDA Version: 12.4" out of nvidia-smi
    $cudaLine = $smi | Select-String -Pattern "CUDA Version:\s+(\d+)\.(\d+)"
    if ($cudaLine -and $cudaLine.Matches.Count -gt 0) {
        $major = [int]$cudaLine.Matches[0].Groups[1].Value
        $minor = [int]$cudaLine.Matches[0].Groups[2].Value
        # PyTorch publishes wheels for cu118, cu121, cu124, cu126 etc.  Pick
        # the highest known wheel that's <= the driver's reported CUDA.
        $known = @(126, 124, 121, 118)
        $combo = ($major * 10) + [math]::Min($minor, 9)
        $picked = $known | Where-Object { $_ -le $combo } | Select-Object -First 1
        if (-not $picked) { $picked = 118 }
        $CudaVersion = "cu$picked"
    } else {
        Write-Warning "Could not parse CUDA version from nvidia-smi output."
        $CudaVersion = "cu124"
    }
}

Write-Host "Detected CUDA target: $CudaVersion"
Write-Host "Reinstalling torch into backend/venv..."

& $venvPython -m pip uninstall -y torch torchvision torchaudio | Out-Host
& $venvPython -m pip install --upgrade torch `
    --index-url "https://download.pytorch.org/whl/$CudaVersion" | Out-Host

# Verify
$verify = & $venvPython -c @"
import torch
print(f'torch={torch.__version__} cuda_available={torch.cuda.is_available()} device_count={torch.cuda.device_count()}')
"@

Write-Host ""
Write-Host "=== Verification ==="
Write-Host $verify

if ($verify -match "cuda_available=True") {
    Write-Host ""
    Write-Host "✓ CUDA torch is active in backend/venv." -ForegroundColor Green
    Write-Host "  Restart the backend (python run.py) for changes to take effect."
} else {
    Write-Warning "torch installed but CUDA not detected at runtime."
    Write-Warning "Check your NVIDIA driver version vs the wheel CUDA version."
}
