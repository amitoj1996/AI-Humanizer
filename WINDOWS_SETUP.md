# AI Humanizer — Windows Setup & Usage

Everything you need to clone, set up, develop, test, and ship this app on
a Windows PC. Tracks the live state of the repo (latest commit, April 2026).

> Target hardware for the default model profile: a single 8 GB NVIDIA GPU
> (RTX 3070-class) or better. CPU works too, just slower. A 2× RTX 3070
> setup lets you run the 9B rewriter on one card and keep the detector
> warm on the other.

---

## Table of contents

1. [What this app does](#what-this-app-does)
2. [Prerequisites](#prerequisites)
3. [First-time setup](#first-time-setup)
4. [Daily development](#daily-development)
5. [Running tests](#running-tests)
6. [Eval baseline + HC3 corpus](#eval-baseline--hc3-corpus)
7. [Building the Windows installer](#building-the-windows-installer)
8. [Project structure](#project-structure)
9. [Environment variables](#environment-variables)
10. [Editor & rich-text behaviour](#editor--rich-text-behaviour)
11. [Troubleshooting](#troubleshooting)
12. [Phase-by-phase changelog](#phase-by-phase-changelog)
13. [What's next](#whats-next)

---

## What this app does

Fully-local AI text humanizer + detector + authorship tracker. Nothing
leaves your machine. Three things differentiate it from JustDone /
Undetectable.ai / Quillbot:

1. **Privacy** — models run locally via Ollama + HuggingFace. No API calls.
2. **Tamper-evident provenance** — every edit, paste, detection, and
   humanize pass is appended to a SHA-256 hash-chained event log per
   session. Export a writing-process report showing typed vs pasted vs
   AI-assisted authorship with a verifiable integrity proof. Plus an
   *Authoring Replay* tab that scrubs through every save and AI rewrite.
   Nobody else in the humanizer market ships this.
3. **Citation-aware rewriting** — `[Smith 2024]`, `"quotes"`, code,
   and LaTeX are detected and preserved verbatim through humanization.

---

## Prerequisites

Install these first (one-time):

| Tool | Version | Why | Install |
|---|---|---|---|
| **Python** | 3.13.x (NOT 3.14 — pydantic-core incompatibility) | Backend runtime | [python.org](https://www.python.org/downloads/windows/) — tick "Add Python to PATH" |
| **Node.js** | 22 LTS | Frontend build | [nodejs.org](https://nodejs.org/en/download/) |
| **Git** | any recent | Clone / version control | [git-scm.com](https://git-scm.com/download/win) |
| **Ollama** | 0.18+ | Local LLM runtime | [ollama.com/download/windows](https://ollama.com/download/windows) |
| **NVIDIA driver** | 550+ | GPU acceleration | NVIDIA's site (skip if CPU-only) |
| **Inno Setup 6** | 6.x | Windows installer build only — skip until you need it | [jrsoftware.org](https://jrsoftware.org/isinfo.php) |
| **WebView2 Runtime** | Evergreen | Native desktop window for the .exe | Preinstalled on Win11; bundled by our installer for Win10 |

Open a fresh PowerShell after installs so PATH updates take effect:

```powershell
python --version    # 3.13.x
node --version      # v22.x
npm --version       # 10.x
ollama --version    # 0.18.x
git --version
nvidia-smi          # for GPU users — should list your card(s)
```

If `Activate.ps1` later complains about execution policy, run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

---

## First-time setup

### 1. Clone

```powershell
cd $HOME
git clone https://github.com/amitoj1996/AI-Humanizer.git
cd AI-Humanizer
```

### 2. Backend venv + dependencies

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

# CPU torch first — small + fast install.  GPU swap is one command in step 3.
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 3. (NVIDIA only) Swap to GPU torch

We ship a helper that detects `nvidia-smi`, picks the highest-compatible
PyTorch CUDA wheel index (cu118 / cu121 / cu124 / cu126), and reinstalls
torch into your `backend\venv` — verifying `torch.cuda.is_available()` at
the end so you know it worked:

```powershell
cd ..
.\scripts\enable-cuda.ps1
# Expected last line: "✓ CUDA torch is active in backend/venv."
```

You can override the auto-detected version: `.\scripts\enable-cuda.ps1 -CudaVersion cu124`

> The `enable-cuda.ps1` script targets the **dev venv** only. The
> PyInstaller-built installer ships CPU torch; CUDA-in-bundle is on the
> roadmap (see [What's next](#whats-next)).

### 4. Frontend (a **second** PowerShell window)

```powershell
cd $HOME\AI-Humanizer\frontend
npm ci
```

### 5. Pull Ollama models

```powershell
# Default rewriter — 6.6 GB Q4_K_M, fits on a single 8 GB GPU
ollama pull qwen3.5:9b

# Optional fast profile — 3.4 GB
ollama pull qwen3.5:4b

# Confirm
ollama list
```

The Ollama installer registers a Windows background service. If the app
later complains "Ollama is not running", open a PowerShell and run
`ollama serve`, or restart Windows once.

### 6. First launch

Two PowerShell windows:

**Window A — backend** (with venv active)
```powershell
cd $HOME\AI-Humanizer\backend
.\venv\Scripts\Activate.ps1
python run.py
```

First boot logs:
```
Initialising SQLite database...
Loading AI detection models (first run downloads ~1.5 GB)...
```

The first-run download is:

| Model | Size | Purpose |
|---|---|---|
| `roberta-base-openai-detector` | ~500 MB | Binary AI/human classifier |
| `Qwen/Qwen3.5-4B-Base` | ~8 GB on disk | Perplexity / burstiness analysis |
| `sentence-transformers/all-MiniLM-L6-v2` | ~90 MB | Meaning-preservation similarity |

On a slow connection, the 4B perplexity model is the bottleneck. On a
4 GB-or-less GPU, switch to the smaller variant via env var (see
[Environment variables](#environment-variables)).

**Window B — frontend**
```powershell
cd $HOME\AI-Humanizer\frontend
npm run dev
```

Open **http://localhost:3000**. The header model dropdown should populate
with your pulled Ollama models. You're up.

---

## Daily development

Two PowerShell windows, both hot-reload:

```powershell
# A — backend
cd $HOME\AI-Humanizer\backend; .\venv\Scripts\Activate.ps1; python run.py

# B — frontend
cd $HOME\AI-Humanizer\frontend; npm run dev
```

Save a Python file → uvicorn restarts. Save a TSX file → Next.js refreshes.

### Managing Ollama models at runtime

```powershell
ollama list                  # see pulled models
ollama rm <name>             # remove one
ollama pull qwen3.5:9b       # pull or update the default
```

The app's header dropdown switches between any pulled model — the backend
updates its pipeline on the next humanize call.

---

## Running tests

| Test type | Command | When |
|---|---|---|
| Backend unit (fast, offline) | `cd backend; pytest -q` | After backend changes |
| Backend offline-strict | `$env:HF_HUB_OFFLINE="1"; $env:TRANSFORMERS_OFFLINE="1"; pytest -q` | Verify zero network deps |
| Backend eval gate (slow, real models) | `pytest -m eval` | After detector / weight changes |
| Frontend type check | `cd frontend; npx tsc --noEmit` | Before commit |
| Frontend lint | `cd frontend; npm run lint` | Before commit |
| Frontend unit (Vitest) | `cd frontend; npm test` | After recorder / store changes |
| Frontend build | `cd frontend; npm run build` | Before tagging a release |
| End-to-end (Playwright) | `cd frontend; npm run e2e:install` (one-time) then `npm run e2e` | Before PR |

Expected baseline: **80 backend tests** pass offline in ~2 s, **6 Vitest
tests** in ~0.5 s, **2 Playwright specs** in ~30 s.

The Playwright suite uses `run_test_server.py` (FakeRegistry-backed
backend on port 8001) so it doesn't need real models or a running Ollama.

---

## Eval baseline + HC3 corpus

The eval harness is a regression gate on detector quality. Two pieces:

### Step A — pull the HC3 corpus subset (one-time, ~10 MB)

```powershell
cd $HOME\AI-Humanizer\backend
.\venv\Scripts\Activate.ps1
python -m app.eval.fetch_hc3
```

Downloads ~50 samples each from 5 HC3 sources (reddit_eli5, open_qa,
wiki_csai, medicine, finance) — ~250 human + ~250 ChatGPT after
filtering. Writes `hc3_human.json` + `hc3_ai.json` to
`backend\app\eval\samples\`. Each sample carries CC BY-SA attribution
in its `source` field.

The fetcher is deterministic — re-running with the same `SEED` constant
produces the same subset. Bump `SAMPLES_PER_SOURCE` in
`backend\app\eval\fetch_hc3.py` if you want more coverage.

### Step B — generate the baseline

```powershell
python -m app.eval.runner --update-baseline
```

This loads the real detector models (~30 s cold start) and:
1. Scores all `*_human.json` + `*_ai.json` samples in `backend\app\eval\samples\`
   (the runner auto-discovers — drop in more files, no code change needed)
2. Runs the 5 preservation round-trip checks
3. Writes the metrics to `backend\app\eval\baseline.json`

### Step C — commit

```powershell
cd ..
git add backend\app\eval\samples\hc3_*.json `
        backend\app\eval\baseline.json
git commit -m "eval: HC3 corpus subset + initial baseline"
git push
```

After that lands on `main`, the `Eval regression` GitHub workflow stops
short-circuiting (it has a `check-baseline` guard) and starts enforcing
detector accuracy on every push to main. Default tolerance:
`ACCURACY_TOLERANCE = 0.10` — drops over 10 pp from baseline fail CI.
Once your signal is stable you can tighten that toward 0.05 in
`backend\app\eval\runner.py`.

### Run the gate locally any time

```powershell
pytest -m eval -v
```

---

## Building the Windows installer

Produces `AIHumanizerSetup.exe` — a ~2 GB installer that drops a
PyInstaller-frozen bundle into `%LOCALAPPDATA%\Programs\AI Humanizer`,
adds Start Menu + Desktop shortcuts, and detects/installs WebView2 +
Ollama if missing.

### Via GitHub Actions (recommended)

Tag a release:

```powershell
git tag v2.0.0
git push --tags
```

The `Build Windows Installer` workflow runs on `windows-latest`, builds
the installer, and attaches it to the GitHub release. Grab it from the
Releases page.

### Locally

Requires Inno Setup 6 installed (see [Prerequisites](#prerequisites)).

```powershell
cd $HOME\AI-Humanizer
.\windows\build.ps1
```

Output: `windows\output\AIHumanizerSetup.exe`. Full build details and
the Ollama-model-profile picker table in
[windows/README.md](windows/README.md).

---

## Project structure

```
AI-Humanizer/
├── .github/workflows/
│   ├── test.yml              backend pytest + frontend tsc/lint/vitest/build
│   ├── e2e.yml               Playwright smoke tests
│   ├── eval.yml              detector regression gate (main only,
│   │                         skipped until baseline.json exists)
│   └── build-windows.yml     Inno Setup installer on v* tags
├── backend/
│   ├── alembic.ini
│   ├── pytest.ini            `-m "not eval"` excludes the eval gate by default
│   ├── run.py                dev entry point
│   ├── run_test_server.py    Playwright-mode server (FakeRegistry, no models)
│   ├── desktop.py            pywebview launcher for the .app / .exe bundle
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py           slim FastAPI app + lifespan
│   │   ├── config.py         env-var overrides for model picks, DB path
│   │   ├── deps.py           ServiceRegistry + FastAPI dependency functions
│   │   ├── api/              per-domain routers (detection, humanization,
│   │   │                     documents, provenance, import_export, ...)
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── services/         business logic (documents, prosemirror, ...)
│   │   ├── detector/         ensemble: classifier + perplexity + linguistic
│   │   ├── humanizer/        Ollama rewriter + post-process + structural
│   │   │                     + pipeline + preserve (citation-aware)
│   │   ├── provenance/       hash-chain primitives + service + report + replay
│   │   ├── ingest/           PDF/DOCX/MD/TXT import
│   │   ├── export/           DOCX/MD/TXT + process-report export
│   │   ├── eval/             regression-gate runner + golden samples + HC3 fetcher
│   │   └── db/               SQLModel models + Alembic migrations
│   └── tests/                pytest (offline-safe via FakeRegistry)
├── frontend/
│   ├── playwright.config.ts  boots backend + frontend for E2E
│   ├── vitest.config.ts      jsdom + react for recorder unit tests
│   ├── e2e/smoke.spec.ts     happy-path Playwright tests
│   └── src/
│       ├── app/              Next.js App Router pages
│       ├── components/       Tiptap editor + sidebar + report modal + ...
│       ├── lib/              api client, types, provenance recorder + tests
│       └── store/            Zustand stores (app, documents)
├── windows/
│   ├── ai-humanizer.spec     PyInstaller spec (cross-platform)
│   ├── installer.iss         Inno Setup 6 script
│   ├── build.ps1             orchestrator
│   ├── bootstrap/            WebView2 + Ollama silent installers
│   └── README.md             build + install + troubleshooting
├── scripts/
│   ├── enable-cuda.ps1       dev-venv torch CUDA swap helper
│   ├── build-app.sh          macOS .app build helper
│   └── start.sh              macOS dev start helper
├── assets/icon.svg           app icon source
└── WINDOWS_SETUP.md          (this file)
```

---

## Environment variables

Override defaults without touching config files:

| Variable | Default | Purpose |
|---|---|---|
| `AI_HUMANIZER_OLLAMA_MODEL` | `qwen3.5:9b` | Rewriter tag |
| `AI_HUMANIZER_PERPLEXITY_MODEL` | `Qwen/Qwen3.5-4B-Base` | Perplexity LM (use `Qwen/Qwen3.5-0.8B` on small-VRAM machines) |
| `AI_HUMANIZER_CLASSIFIER_MODEL` | `roberta-base-openai-detector` | Binary AI classifier |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API host |
| `AI_HUMANIZER_DATA_DIR` | `%LOCALAPPDATA%\AIHumanizer` | App data root |
| `AI_HUMANIZER_DB_PATH` | `<DATA_DIR>\aih.db` | SQLite DB path |
| `HF_HUB_OFFLINE` | — | Set to `1` to block HuggingFace network calls |
| `TRANSFORMERS_OFFLINE` | — | Set to `1` to enforce offline Transformers |

Example — use the smaller perplexity model on a 4 GB GPU:

```powershell
$env:AI_HUMANIZER_PERPLEXITY_MODEL = "Qwen/Qwen3.5-0.8B"
python run.py
```

---

## Editor & rich-text behaviour

The editor is Tiptap / ProseMirror. Revisions store ProseMirror JSON, so
formatting survives the round-trip end-to-end:

- Markdown shortcuts (`# heading`, `**bold**`, `*italic*`, `- list`,
  `> quote`, `` ` ` ``) render in the editor AND survive
  save / load / restore / `.md` export.
- Detection / humanization operate on a plain-text projection of the doc
  — those models don't use formatting and we don't want them seeing
  markdown noise.
- Auto-saves after **detection** preserve the structured doc; auto-saves
  after **humanize** are plain text (the LLM returns a string). Either
  way the editor reconstructs a JSON view on the next user keystroke.
- Existing plain-text revisions in your DB keep working — they get
  `format='text'` from the migration's server default.

The provenance recorder listens on ProseMirror transactions (not raw DOM
input events), so per-step typed/pasted/deleted classification is
accurate, IME composition is handled, and undo/redo is logged as
`manual_edit` rather than counterfeit fresh authorship.

---

## Troubleshooting

### "This app can't run on your PC" / SmartScreen
Unsigned installers trigger SmartScreen. Click **More info → Run anyway**.
Code signing is not on the roadmap right now (per project direction).

### First launch takes forever
HuggingFace models are downloading. Watch
`%LOCALAPPDATA%\..\.cache\huggingface\hub` grow. Once cached, set
`HF_HUB_OFFLINE=1` to enforce offline use on subsequent runs.

### `ModuleNotFoundError: No module named 'pydantic_core'`
Wrong Python version. Pydantic-core doesn't support Python 3.14 yet.
Use 3.13.

### `ExecutionPolicy` blocks `Activate.ps1`
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Ollama not found from the app
Confirm Ollama is running:
```powershell
curl http://localhost:11434/api/tags
```
Should return JSON. If not, `ollama serve` in a terminal, or restart
Windows once so the service registers.

### `torch.cuda.is_available()` returns False
1. `nvidia-smi` works? If not, fix the driver.
2. You probably have CPU torch. Run `.\scripts\enable-cuda.ps1` from the
   repo root with the venv active.

### Playwright tests hang on "create project" dialog
Browser missing. Run `npx playwright install chromium` from `frontend\`.

### Port 8000 / 3000 already in use
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess
Stop-Process -Id <pid>
```

### Antivirus flags the PyInstaller bundle
Expected — unsigned ML binaries trigger heuristics. Submit to Windows
Defender's false-positive portal after release; reputation accrues with
a stable cert over a few hundred installs.

---

## Phase-by-phase changelog

| Phase | Commit | What shipped |
|---|---|---|
| 0 | `f9449b4` | Foundation refactor: dependency-injected FastAPI, Zustand store, 12 split components, CI, 12 smoke tests |
| 1 | `6f1d2ad` | SQLite + SQLModel: projects, documents, revisions with SHA-256 dedup; sidebar, doc header, revision timeline |
| 2 | `e951551` | **The moat** — tamper-evident provenance with hash chain, session lifecycle, writing-process report with authorship breakdown |
| 3 | `2354ac7` | Import/export: PDF (PyMuPDF4LLM), DOCX (python-docx), MD, TXT; process-report export in MD + DOCX |
| 4 | `07e0314` | Windows installer: PyInstaller onedir + Inno Setup + WebView2/Ollama bootstrap; cross-platform spec |
| 5 | `cfd634a` | Citation-aware rewriting: regex-detected citations/quotes/code/LaTeX survive humanization verbatim |
| 6 | `74619ff` | Trust fixes from review: test isolation, offline fonts, NLTK removal, DOCX ordering, seal verification, Alembic migrations |
| 7 | `0c815a0` + `8c5cf2d` | Eval harness, Playwright smoke tests, two more provenance event-loss fixes |
| 8 | `59f4a45` + `c2547b9` | **Authoring replay** + CUDA dev helper + eval corpus expansion (8→14) |
| 9 | `00081e8` + `ce2728f` | **Tiptap / ProseMirror editor migration** + transaction-level recorder |
| 10 | `cd12ad8` + `5be285a` | **Rich-text revisions** (ProseMirror JSON in `Revision.content`), Vitest recorder unit tests |
| HC3 | `7cb1342` | HC3 fetcher script + sample-file auto-discovery in the eval runner |

---

## What's next

Browser extension and code signing are explicitly **dropped from the roadmap**.

Of the remaining items:

- ✅ Tiptap migration (Phase 9)
- ✅ Rich-text revisions (Phase 10)
- ✅ Frontend recorder unit tests (Phase 10)
- ✅ HC3 corpus + auto-discovery (run-once script, ready)
- ⏳ **CUDA inside the PyInstaller bundle** — `enable-cuda.ps1` works for
  the dev venv but the `AIHumanizerSetup.exe` ships CPU torch. Plan:
  ship CPU torch, on first launch detect `nvidia-smi`, download the
  matching CUDA wheel into `%LOCALAPPDATA%\AIHumanizer\torch-cuda\`,
  insert at the front of `sys.path` to shadow the bundled torch, then
  restart the Python process. Estimated 3-4 days. Caveat from the
  PyInstaller + PyTorch issue threads: parse the driver-reported CUDA
  version and pick the highest-compatible wheel, otherwise DLL-load
  failures on driver/wheel mismatches.
