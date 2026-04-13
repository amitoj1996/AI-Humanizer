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
