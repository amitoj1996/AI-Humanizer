# Windows build

Produces a Windows installer (`AIHumanizerSetup.exe`) that ships:

- The PyInstaller-frozen FastAPI backend + pre-built Next.js UI
- CPU-only PyTorch (CUDA is upgraded post-install if an NVIDIA GPU is detected — TODO)
- Automatic detection + on-demand install of prerequisites:
  - **WebView2 Evergreen Runtime** — silently, if missing (preinstalled on Win11)
  - **Ollama** — interactive installer, because silent mode is flaky
    ([ollama#7969](https://github.com/ollama/ollama/issues/7969))

Models (Qwen 3.5, RoBERTa, sentence-transformers) are **not bundled** — they're
downloaded on first launch to the user's HuggingFace cache. That keeps the
installer ~1.5–2 GB instead of 4+ GB.

## Model profiles (Ollama)

Verified against official releases as of April 2026. Pull the model you
want and select it from the app's Models dropdown.

| Profile | Model | Size (Q4_K_M) | Notes |
|---|---|---|---|
| **Default** (Balanced) | `qwen3.5:9b` | 6.6 GB | Fits on a single 8 GB GPU (e.g. RTX 3070). Ollama keeps single-GPU-fit models on one card for best latency. |
| **Fast** | `qwen3.5:4b` | 3.4 GB | Snappier UI, leaves room for concurrent detector work on the same GPU. |
| **Reasoning** (optional) | `deepseek-r1:8b` | 5.2 GB | Better analytical rewriting; reasoning traces can push style harder than pure rewriters. |
| **Quality experiment** | `mistral-small3.2:24b` | 15 GB | Will span both GPUs on dual-8 GB setups — worse latency, best raw quality. |
| **Skip** | `llama4` (67 GB min) | — | Too big for this hardware tier. |

Pull the default after install:

```powershell
ollama pull qwen3.5:9b
```

Override defaults via environment variables (e.g. on CPU-only machines
where a 4 B-param perplexity model is too slow per sentence):

```powershell
$env:AI_HUMANIZER_OLLAMA_MODEL     = "qwen3.5:4b"
$env:AI_HUMANIZER_PERPLEXITY_MODEL = "Qwen/Qwen3.5-0.8B"
```

## Building

### Via GitHub Actions (recommended)

Tag a release:

```bash
git tag v2.0.0 && git push --tags
```

The `Build Windows Installer` workflow runs on `windows-latest`, builds the
installer, and attaches it to the GitHub release.

### Locally (Windows machine)

Prerequisites:
- Python 3.13 (`python` on PATH)
- Node.js 22 (`npm` on PATH)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`iscc` on PATH or at the
  default install location)

From the repo root:

```powershell
.\windows\build.ps1
```

This will:
1. Build the Next.js static export → `backend/static/`
2. Create a fresh build venv and install CPU torch + deps + PyInstaller
3. Freeze the app → `dist/AI Humanizer/`
4. Download WebView2 + Ollama installers into `windows/bootstrap/`
5. Run Inno Setup → `windows/output/AIHumanizerSetup.exe`

## Installing

Double-click `AIHumanizerSetup.exe`. The installer is per-user (no admin
rights required) and installs to `%LOCALAPPDATA%\Programs\AI Humanizer`.

### SmartScreen warning

Unsigned builds trigger "Windows protected your PC" — the cheapest fix is
[Azure Trusted Signing](https://learn.microsoft.com/en-us/azure/trusted-signing/)
(~$10/mo, no HSM required). Until we sign: click **More info → Run anyway**.

## Uninstalling

Standard "Add or Remove Programs" entry. Uninstall removes the app bundle
but **keeps user data** at `%LOCALAPPDATA%\AIHumanizer\aih.db` so documents
survive reinstalls.

## What's not in v1

- **Auto-updates** via Velopack — deferred; v1 users download new installers
- **Code signing** — deferred
- **CUDA upgrade on install** — planned; for now CPU-only PyTorch is bundled
- **Marker OCR** for scanned PDFs — on-demand download when a scanned PDF is imported

## Troubleshooting

**"This app can't run on your PC"** — the bundle is x64-only. 32-bit Windows is unsupported.

**First launch takes 5+ minutes** — models are downloading (~1.5 GB from HuggingFace). Watch the app window; it'll show "Loading models..." until ready.

**"Ollama is not running"** — open Command Prompt and run `ollama serve`, or reboot after install (Ollama registers as a background service).

**Antivirus flags the installer** — unsigned PyInstaller bundles sometimes trigger heuristics. Submit a false-positive report to your vendor; we'll sign in a future release.
