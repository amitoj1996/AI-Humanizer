# End-to-end Windows build.
#
# 1. Builds the Next.js static export into backend/static
# 2. Creates a clean venv and installs CPU-only torch + all requirements
# 3. Runs PyInstaller with the spec → dist/AI Humanizer/
# 4. Downloads WebView2 + Ollama installers into windows/bootstrap
# 5. Runs Inno Setup to produce windows/output/AIHumanizerSetup.exe
#
# Usage (from repo root):
#   .\windows\build.ps1

param(
  [switch]$SkipFrontend = $false,
  [switch]$SkipPrereqs = $false
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Frontend = Join-Path $Root "frontend"
$Backend = Join-Path $Root "backend"
$Windows = Join-Path $Root "windows"
$Bootstrap = Join-Path $Windows "bootstrap"
$Venv = Join-Path $Backend "build-venv"

Write-Host "==> AI Humanizer Windows build"
Write-Host "    root:     $Root"

# ---- 1. Build frontend ----
if (-not $SkipFrontend) {
    Write-Host "==> [1/5] Building frontend static export..."
    Push-Location $Frontend
    npm install --silent
    npm run build
    Pop-Location

    $staticDir = Join-Path $Backend "static"
    if (Test-Path $staticDir) { Remove-Item -Recurse -Force $staticDir }
    Copy-Item -Recurse (Join-Path $Frontend "out") $staticDir
}

# ---- 2. Create build venv ----
Write-Host "==> [2/5] Creating build venv..."
if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
python -m venv $Venv
$pip = Join-Path $Venv "Scripts\pip.exe"
$py  = Join-Path $Venv "Scripts\python.exe"
& $pip install --upgrade pip --quiet

# CPU-only torch to keep bundle under ~2 GB.  CUDA wheels are ~2.5 GB alone.
& $pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet
& $pip install -r (Join-Path $Backend "requirements.txt") --quiet
& $pip install pyinstaller --quiet

# ---- 3. PyInstaller ----
Write-Host "==> [3/5] Running PyInstaller..."
Push-Location $Root
& $py -m PyInstaller --noconfirm --clean (Join-Path $Windows "ai-humanizer.spec")
Pop-Location

# ---- 4. Download prereqs ----
if (-not $SkipPrereqs) {
    Write-Host "==> [4/5] Downloading WebView2 + Ollama installers..."
    & (Join-Path $Bootstrap "download-prereqs.ps1")
}

# ---- 5. Inno Setup ----
Write-Host "==> [5/5] Building installer with Inno Setup..."
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
}
if (-not (Test-Path $iscc)) {
    Write-Error "Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php"
    exit 1
}

Push-Location $Windows
& $iscc "installer.iss"
Pop-Location

Write-Host ""
Write-Host "==> Done."
Write-Host "    Installer: $Windows\output\AIHumanizerSetup.exe"
