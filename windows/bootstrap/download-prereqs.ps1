# Downloads WebView2 + Ollama installers into windows/bootstrap/ so the
# Inno Setup script can bundle them.
#
# Run before iscc: .\windows\bootstrap\download-prereqs.ps1

param(
  [string]$BootstrapDir = (Join-Path $PSScriptRoot "")
)

$ErrorActionPreference = "Stop"

$webview2Url = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"  # Evergreen bootstrapper
$ollamaUrl   = "https://ollama.com/download/OllamaSetup.exe"

$webview2Out = Join-Path $BootstrapDir "MicrosoftEdgeWebview2Setup.exe"
$ollamaOut   = Join-Path $BootstrapDir "OllamaSetup.exe"

if (-not (Test-Path $webview2Out)) {
    Write-Host "Downloading WebView2 bootstrapper..."
    Invoke-WebRequest -Uri $webview2Url -OutFile $webview2Out -UseBasicParsing
}

if (-not (Test-Path $ollamaOut)) {
    Write-Host "Downloading Ollama installer (~500 MB)..."
    Invoke-WebRequest -Uri $ollamaUrl -OutFile $ollamaOut -UseBasicParsing
}

Write-Host "Prerequisites ready in: $BootstrapDir"
