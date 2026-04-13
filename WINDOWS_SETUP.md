# AI Humanizer — Windows Setup & Usage

Everything you need to clone, set up, develop, test, and ship this app on
a Windows PC. Written for the April 2026 state of the repo (commit `0c815a0`).

> Target hardware for the default model profile: a single 8 GB NVIDIA GPU
> (RTX 3070-class) or better. Works on CPU too, just slower. A 2× RTX 3070
> setup lets you run the 9B rewriter on one card and keep the detector
> warm on the other.

---

## Table of contents
1. [What this app does](#what-this-app-does)
2. [Prerequisites](#prerequisites)
3. [First-time setup](#first-time-setup)
4. [Daily development](#daily-development)
5. [Running tests](#running-tests)
6. [Generating the eval baseline](#generating-the-eval-baseline)
7. [Building the Windows installer](#building-the-windows-installer)
8. [Project structure](#project-structure)
9. [Environment variables](#environment-variables)
10. [Troubleshooting](#troubleshooting)
11. [Phase-by-phase changelog](#phase-by-phase-changelog)
12. [Phase 7 — what we just did](#phase-7--what-we-just-did)

---

## What this app does

Fully-local AI text humanizer + detector + authorship tracker. Nothing
leaves your machine. Three things differentiate it from JustDone /
Undetectable.ai / Quillbot:

1. **Privacy** — models run locally via Ollama + HuggingFace. No API calls.
2. **Tamper-evident provenance** — every edit, paste, detection, and
   humanize pass is appended to a SHA-256 hash-chained event log per
   session. Export a writing-process report showing typed vs pasted vs
   AI-assisted authorship with a verifiable integrity proof. Nobody else
   in the humanizer market ships this.
3. **Citation-aware rewriting** — `[Smith 2024]`, `"quotes"`, code,
   and LaTeX are detected and preserved verbatim through humanization.

---

## Prerequisites

Install these first (one-time):

| Tool | Version | Why | Install |
|---|---|---|---|
| **Python** | 3.13.x (NOT 3.14 — pydantic-core incompatibility) | Backend runtime | [python.org](https://www.python.org/downloads/windows/) — check "Add Python to PATH" |
| **Node.js** | 22 LTS | Frontend build | [nodejs.org](https://nodejs.org/en/download/) |
| **Git** | any recent | Clone / version control | [git-scm.com](https://git-scm.com/download/win) |
| **Ollama** | 0.18+ | Local LLM runtime | [ollama.com/download/windows](https://ollama.com/download/windows) |
| **Inno Setup 6** | 6.x | Windows installer build only | [jrsoftware.org](https://jrsoftware.org/isinfo.php) |
| **NVIDIA driver** | 550+ | GPU acceleration | NVIDIA's site (skip if CPU-only) |
| **WebView2 Runtime** | Evergreen | Native desktop window | Preinstalled on Win11; `MicrosoftEdgeWebview2Setup.exe` on Win10 |

Open a fresh PowerShell after installs so PATH updates take effect.

Verify:
```powershell
python --version        # Python 3.13.x
node --version          # v22.x
npm --version           # 10.x
ollama --version        # 0.18.x
git --version
```

---

## First-time setup

### 1. Clone

```powershell
cd $HOME
git clone https://github.com/amitoj1996/AI-Humanizer.git
cd AI-Humanizer
```

### 2. Backend

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1

# PowerShell execution-policy gotcha — if Activate.ps1 is blocked, run ONCE:
#   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

python -m pip install --upgrade pip

# Install CPU-only torch first (faster); CUDA wheel swap happens later if
# you have an NVIDIA GPU. Skip this line if you already have CUDA torch.
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

### 2a. (Optional, NVIDIA only) Upgrade to CUDA torch

```powershell
nvidia-smi                 # confirm driver / CUDA version, should be 12.x
pip uninstall -y torch
pip install torch --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print('CUDA:', torch.cuda.is_available(), 'devices:', torch.cuda.device_count())"
# Expected: CUDA: True, devices: 2 (for your 2x RTX 3070)
```

### 3. Frontend

New PowerShell tab (leave the venv one for backend):

```powershell
cd $HOME\AI-Humanizer\frontend
npm ci
```

### 4. Ollama models

```powershell
# Default rewriter — 6.6 GB, fits on one 8 GB GPU
ollama pull qwen3.5:9b

# Fast profile (optional) — 3.4 GB
ollama pull qwen3.5:4b

# Start the Ollama background service (if not already running)
ollama serve
```

Keep `ollama serve` running in its own terminal (or confirm the Windows
service is active).

### 5. HuggingFace models (auto-downloaded on first run)

The backend auto-downloads on first launch (~1.5 GB total):

- `roberta-base-openai-detector` — binary AI classifier (~500 MB)
- `Qwen/Qwen3.5-4B-Base` — perplexity LM (~8 GB **on-disk** but we use CPU/GPU weights selectively)
- `sentence-transformers/all-MiniLM-L6-v2` — similarity checker (~90 MB)

On a slow connection the 4B perplexity model takes a while. If that's too
heavy, override to the 0.8B variant (see [Environment variables](#environment-variables)).

### 6. First launch

Two terminals, in this order:

**Terminal A — backend**
```powershell
cd $HOME\AI-Humanizer\backend
.\venv\Scripts\Activate.ps1
python run.py
```
First boot shows `Loading AI detection models (first run downloads ~1.5 GB)...`
— be patient. Subsequent boots use the HuggingFace cache.

**Terminal B — frontend**
```powershell
cd $HOME\AI-Humanizer\frontend
npm run dev
```

Open http://localhost:3000. If all four services are up (Ollama, backend,
frontend, WebView2) you should see the Ollama model dropdown populate in
the header and be able to create a project.

---

## Daily development

Once you've done the first-time setup, the everyday loop is:

```powershell
# Terminal A
cd $HOME\AI-Humanizer\backend
.\venv\Scripts\Activate.ps1
python run.py

# Terminal B
cd $HOME\AI-Humanizer\frontend
npm run dev
```

Both support hot reload — save a Python file, uvicorn restarts;
save a TSX file, Next.js refreshes the browser.

### Managing Ollama models

```powershell
ollama list                        # see pulled models
ollama rm <name>                   # remove one
ollama pull qwen3.5:9b             # pull/update the default
```

In the app's header dropdown you can switch between any pulled model at
runtime — the backend updates the pipeline on the next humanize call.

---

## Running tests

### Unit / integration tests (fast, offline, no models)
```powershell
cd $HOME\AI-Humanizer\backend
.\venv\Scripts\Activate.ps1
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
pytest -q
```
Expected: **69 passed, 2 deselected** in ~4 seconds.

### Frontend type check + lint + build
```powershell
cd $HOME\AI-Humanizer\frontend
npx tsc --noEmit
npm run lint
npm run build
```

### End-to-end (Playwright) tests

Requires frontend + backend deps installed, but no HuggingFace cache and
no Ollama — the `run_test_server.py` entry point uses a FakeRegistry and
a mocked Ollama client.

```powershell
cd $HOME\AI-Humanizer\frontend
npm run e2e:install        # one-time: installs Chromium for Playwright (~200 MB)
npm run e2e                # runs the smoke tests
```

Playwright auto-starts both servers (backend on :8001, frontend on :3001)
and tears them down afterwards.

### Eval regression suite (slow, loads real models)
See the [next section](#generating-the-eval-baseline).

---

## Generating the eval baseline

The eval harness is a regression gate on detector quality. It's off by
default because it loads real models (~30 s cold start).

### First time — set the baseline

```powershell
cd $HOME\AI-Humanizer\backend
.\venv\Scripts\Activate.ps1
python -m app.eval.runner --update-baseline
```

This will:
1. Load RoBERTa + Qwen 3.5-4B + sentence-transformers
2. Score the 8 human + 8 AI labelled samples in `app/eval/samples/`
3. Run the 5 preservation round-trip checks
4. Write the results to `app/eval/baseline.json`

Commit that file:
```powershell
git add backend/app/eval/baseline.json
git commit -m "eval: set baseline from my machine"
git push
```

From now on, every CI run (and `pytest -m eval` locally) compares against
that snapshot. `ACCURACY_TOLERANCE = 0.10` — if accuracy drops more than
10 pp from baseline, CI fails.

### After a change that might affect detection
```powershell
pytest -m eval -v          # runs the regression gate
```

### Expanding the golden set
Edit `backend/app/eval/samples/human.json`, `ai.json`, or `preserve.json`
and re-run `--update-baseline`.

---

## Building the Windows installer

You'll produce `AIHumanizerSetup.exe` — a ~2 GB installer that drops a
PyInstaller-frozen app into `%LOCALAPPDATA%\Programs\AI Humanizer` and
handles WebView2 + Ollama detection.

### Via GitHub Actions (recommended)
```powershell
git tag v2.0.0
git push --tags
```
The `Build Windows Installer` workflow runs on `windows-latest`, builds
the installer, and attaches it to the GitHub release. Grab it from the
Releases page.

### Locally
```powershell
cd $HOME\AI-Humanizer
.\windows\build.ps1
```
Outputs `windows\output\AIHumanizerSetup.exe`.

Details and model-profile tables in [windows/README.md](windows/README.md).

---

## Project structure

```
AI-Humanizer/
├── .github/workflows/
│   ├── test.yml              backend + frontend fast tests
│   ├── e2e.yml               Playwright smoke tests
│   ├── eval.yml              detector regression gate (main only)
│   └── build-windows.yml     Inno Setup installer on v* tags
├── backend/
│   ├── alembic.ini
│   ├── pytest.ini            `-m "not eval"` excludes the eval gate by default
│   ├── run.py                dev entry point
│   ├── run_test_server.py    Playwright-mode server (fakes, no models)
│   ├── desktop.py            pywebview launcher for the .app / .exe bundle
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py           slim FastAPI app + lifespan
│   │   ├── config.py         env-var overrides for model picks, DB path
│   │   ├── deps.py           ServiceRegistry + FastAPI dependency functions
│   │   ├── api/              per-domain routers (detection, humanization,
│   │   │                     documents, provenance, import_export, ...)
│   │   ├── schemas/          Pydantic request/response models
│   │   ├── services/         business logic (documents, revisions)
│   │   ├── detector/         ensemble: classifier + perplexity + linguistic
│   │   ├── humanizer/        Ollama rewriter, rule-based post-processor,
│   │   │                     structural rewriter, pipeline, preserve
│   │   ├── provenance/       hash-chain primitives + service + service report
│   │   ├── ingest/           PDF/DOCX/MD/TXT import
│   │   ├── export/           DOCX/MD/TXT + process-report export
│   │   ├── eval/             regression-gate runner + golden samples
│   │   └── db/               SQLModel models + Alembic migrations
│   └── tests/
│       ├── conftest.py       FakeRegistry install + per-test tmp DB
│       ├── test_api.py
│       ├── test_documents.py
│       ├── test_provenance.py
│       ├── test_import_export.py
│       ├── test_preserve.py
│       └── test_eval.py      marked @pytest.mark.eval — slow regression gate
├── frontend/
│   ├── playwright.config.ts  boots backend + frontend for E2E
│   ├── e2e/smoke.spec.ts     happy-path Playwright tests
│   └── src/
│       ├── app/              Next.js App Router pages
│       ├── components/       13 components, each focused
│       ├── lib/              api client, types, provenance recorder
│       └── store/            Zustand stores (app, documents)
├── windows/
│   ├── ai-humanizer.spec     PyInstaller spec (cross-platform)
│   ├── installer.iss         Inno Setup 6 script
│   ├── build.ps1             orchestrator
│   ├── bootstrap/            WebView2 + Ollama silent installers
│   └── README.md             build + install + troubleshooting
├── scripts/                  macOS .app build + dev start helpers
├── assets/icon.svg           app icon source
└── WINDOWS_SETUP.md          (this file)
```

---

## Environment variables

Override defaults without touching config files:

| Variable | Default | Purpose |
|---|---|---|
| `AI_HUMANIZER_OLLAMA_MODEL` | `qwen3.5:9b` | Rewriter tag |
| `AI_HUMANIZER_PERPLEXITY_MODEL` | `Qwen/Qwen3.5-4B-Base` | Perplexity LM (try `Qwen/Qwen3.5-0.8B` on CPU) |
| `AI_HUMANIZER_CLASSIFIER_MODEL` | `roberta-base-openai-detector` | Binary AI classifier |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API host |
| `AI_HUMANIZER_DATA_DIR` | `%LOCALAPPDATA%\AIHumanizer` | App data root |
| `AI_HUMANIZER_DB_PATH` | `<DATA_DIR>\aih.db` | SQLite DB path |
| `HF_HUB_OFFLINE` | — | Set to `1` to block HuggingFace network calls |
| `TRANSFORMERS_OFFLINE` | — | Set to `1` to enforce offline Transformers |

Example (use the faster-smaller perplexity model on a 4 GB GPU machine):
```powershell
$env:AI_HUMANIZER_PERPLEXITY_MODEL = "Qwen/Qwen3.5-0.8B"
python run.py
```

---

## Troubleshooting

### "This app can't run on your PC" / SmartScreen
We don't code-sign yet (Phase 4 deferred this). Click **More info → Run anyway**.
Plan to fix with Azure Trusted Signing ($10/mo) in a future release.

### First launch takes forever
Models are downloading. The backend is fine, just wait. Watch
`%LOCALAPPDATA%\..\.cache\huggingface\hub` grow, or enable offline mode
if you've already downloaded once.

### `ModuleNotFoundError: No module named 'pydantic_core'`
Wrong Python version. Pydantic-core doesn't support Python 3.14 yet.
Use 3.13.

### `ExecutionPolicy` blocks `Activate.ps1`
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Ollama not found from the app
Confirm `ollama serve` is running in a terminal or as a Windows service.
Test: `curl http://localhost:11434/api/tags` — should return JSON with
your pulled models.

### `torch.cuda.is_available()` returns False
1. `nvidia-smi` works? If not, fix the driver.
2. You have the CPU-only torch. Reinstall with the CUDA index URL.

### Playwright tests hang on "create project" dialog
Your Windows build is missing a CDP feature. Reinstall with
`npx playwright install chromium`.

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

| Phase | Commit prefix | What shipped |
|---|---|---|
| 0 | `f9449b4` | Foundation refactor: dependency-injected FastAPI, Zustand store, 12 split components, CI (GH Actions), 12 smoke tests |
| 1 | `6f1d2ad` | SQLite + SQLModel: projects, documents, revisions with SHA-256 dedup; sidebar, doc header, revision timeline |
| 2 | `e951551` | **The moat** — Tamper-evident provenance with hash chain, session lifecycle, writing-process report with authorship breakdown |
| 3 | `2354ac7` | Import/export: PDF (PyMuPDF4LLM), DOCX (python-docx), MD, TXT; process-report export in MD + DOCX |
| 4 | `07e0314` | Windows installer: PyInstaller onedir + Inno Setup + WebView2/Ollama bootstrap; cross-platform spec |
| 5 | `cfd634a` | Citation-aware rewriting: regex-detected citations/quotes/code/LaTeX survive humanization verbatim |
| 6 | `74619ff` | Trust fixes from code review: test isolation (67 tests pass offline in 1.7 s), offline fonts, NLTK removal, DOCX ordering, seal verification, Alembic migrations |
| 7 | `0c815a0` | Eval harness, Playwright smoke tests, two more provenance event-loss bug fixes |
| 7-fix | `8c5cf2d` | Review fixes: cross-session contamination, eval gate enforcement, Playwright hermeticity |
| 8 | `59f4a45` | **Authoring replay** + CUDA dev helper + eval corpus expansion (8→14) |

---

## Phase 8 — Authoring Replay (the headline feature)

The provenance hash chain we shipped in Phase 2 now powers a **scrubbable
history view of the document** — the same product surface as Grammarly
Authorship and Turnitin's Authorship Dashboard, but local.

- **Backend** — `app/provenance/replay.py` walks revisions + AI-rewrite
  events into a time-sorted snapshot list; the API exposes
  `GET /api/documents/{id}/provenance/replay`.
- **Frontend** — new `Authoring Replay` tab in the Writing Process Report
  modal with a scrubber, colour-coded tick marks (revision = green,
  AI rewrite = purple, merged = striped), per-snapshot metadata, and a
  reconstructed-content viewer with copy-to-clipboard.
- **CUDA dev helper** — `scripts\enable-cuda.ps1` detects `nvidia-smi`,
  picks the highest matching PyTorch wheel index, and reinstalls torch
  into `backend\venv`. Verifies `torch.cuda.is_available()` before
  declaring success.
- **Eval corpus** — grew from 8+8 to 14+14 hand-curated samples; bigger
  signal for the regression gate without licensing fragility.

### Honest scope
- Per-keystroke replay (sub-revision granularity) needs cursor-position
  tracking the textarea-based recorder doesn't currently capture. Every
  *save* and every *AI rewrite* is a navigable frame, which is what
  matters for academic-integrity / authorship-proof use cases. To get
  per-keystroke we'd need the Tiptap migration (see Phase 9 below).
- CUDA helper targets the dev venv only — the PyInstaller-frozen Windows
  installer still ships CPU torch. CUDA inside the bundle is a separate
  problem (see Phase 9).

---

## ⚠️ Known interim limitation (Phase 9 / Tiptap)

The editor is now ProseMirror-based, but the **app's data model still
round-trips plain text only**.

- You can use Markdown shortcuts in the editor (`# heading`, `**bold**`,
  `- list`, `> quote`, `` ` ` `` for code) and they render correctly
  *while you're typing*.
- But on **save / detect / humanize / document switch / restore**, all
  formatting is stripped. The editor state goes through `editor.getText()`
  before hitting the store, the backend, and revisions.
- Net effect: you can create a heading, but next time you open the
  document it's just a plain paragraph.

This is a deliberate v1 trade-off to ship the editor without a schema
migration. The next phase is to extend `Revision.content` to hold
ProseMirror JSON (with a `format` column for backwards compat) so
formatting survives the round-trip end-to-end.

---

## Phase 9 candidates — what's next, in priority order

These three are the remaining serious work. Browser extension and code
signing are explicitly **dropped from the roadmap**.

### 1. Tiptap / ProseMirror editor migration (highest leverage)

**Why**: Replaces the textarea with a real rich editor. Unlocks
per-keystroke replay (since ProseMirror transactions are typed semantic
operations, not blind DOM input events), enables formatting preservation
through humanize, and gives us track-changes / comment-thread surface for
free if we want them later. Turns the app from "smart textarea" into a
proper writing tool.

**How** (researched April 2026):
- Tiptap's `onTransaction` hook intercepts every ProseMirror transaction
  before it's applied — that's the exact integration point our recorder
  needs. Existing community projects do exactly this:
  [chenyuncai/tiptap-track-change-extension](https://deepwiki.com/chenyuncai/tiptap-track-change-extension/2.2-transaction-processing)
  is a working reference for transaction-level change tracking with full
  IME / collaborative-edit / undo-redo handling.
- Tiptap is framework-agnostic; the React bindings (`@tiptap/react`) work
  cleanly inside Next.js client components. Replace `<textarea>` in
  `TextInput.tsx` with `<EditorContent editor={editor} />` and migrate
  the recorder hook to listen on `editor.on('transaction', ...)` instead
  of DOM `beforeinput`.
- Document storage: store ProseMirror's JSON representation
  (`editor.getJSON()`) in `Revision.content` instead of plain text. Add a
  `format` column (`text` vs `prosemirror`) so existing revisions stay
  loadable. Extract plain text via `editor.getText()` for the detector.
- Estimated effort: 1 week. Touches editor, recorder, revision storage
  schema, replay (gain per-step granularity), provenance reporting.
- References:
  [Tiptap concepts](https://tiptap.dev/docs/editor/core-concepts/introduction),
  [ProseMirror transactions](https://tiptap.dev/docs/editor/core-concepts/prosemirror).

### 2. CUDA inside the PyInstaller bundle

**Why**: `enable-cuda.ps1` works for the dev venv but the
`AIHumanizerSetup.exe` installer ships CPU-only torch. Users without a
dev environment can't get GPU acceleration today.

**How** (researched April 2026):
- The torch CUDA wheels are ~2.5 GB each, so we can't bundle them all
  in the installer (which is already ~1.5 GB).
- Recommended pattern from the
  [PyInstaller + PyTorch discussion threads](https://github.com/pyinstaller/pyinstaller/issues/7175):
  ship CPU torch in the bundle, then on first launch:
  1. Detect `nvidia-smi` via subprocess
  2. Download the matching CUDA wheel (cu124 etc.) into
     `%LOCALAPPDATA%\AIHumanizer\torch-cuda\`
  3. Insert that path at the front of `sys.path` so it shadows the
     bundled torch
  4. Restart the Python process so the new torch is loaded clean
- Risks called out in the threads: DLL-load failures when CUDA driver
  version is older than the wheel's CUDA version (e.g. mixing cu124
  bundled DLLs with a driver that only supports cu118). Mitigate by
  parsing the driver-reported CUDA from `nvidia-smi` (we already do this
  in `enable-cuda.ps1`) and downloading the highest compatible wheel.
- Estimated effort: 3-4 days. Mostly `desktop.py` first-launch logic plus
  installer UI for "(optional) GPU acceleration: 2.5 GB extra download".

### 3. Real frontier eval corpus (HC3)

**Why**: The hand-curated 14+14 samples catch obvious regressions but
don't have statistical signal. A real benchmark would let us claim
honest detector accuracy numbers and do A/B comparisons against
ensemble-weight tweaks.

**How** (researched April 2026):
- [HC3 (Hello-SimpleAI/HC3)](https://huggingface.co/datasets/Hello-SimpleAI/HC3)
  is the standard human-vs-ChatGPT corpus: ~37k human replies + ~37k
  ChatGPT outputs, sourced from Reddit ELI5, Quora, StackExchange and
  topic-tagged (medicine, finance, etc.).
- License: **CC BY-SA**, redistributable with attribution. We can pull
  a 500-1000 sample slice into `app/eval/samples/hc3_subset.json` and
  ship it in the repo without legal risk.
- The follow-up
  [HC3 Plus](https://arxiv.org/abs/2309.02731) corpus (semantic-invariant
  variants) is also CC BY-SA and would be a natural Phase 10 expansion
  for paraphrasing-attack robustness testing.
- Estimated effort: 1-2 days. Add an `app/eval/fetch_hc3.py` script that
  downloads + samples + filters the corpus once, regenerate baseline,
  bump `ACCURACY_TOLERANCE` from 0.10 toward 0.05 since signal will be
  much stronger.

---

## Phase 7 — what we shipped earlier

Phase 7 answered two external-review demands: **rigor** (eval harness) and
**integrity completeness** (provenance event-loss fixes).

### 1. Provenance event-loss fixes
Two real bugs in the "complete authorship proof" feature:

**Bug A — tab close loses the last keystrokes.** The `beforeunload` handler
only sealed the session; it never flushed the in-memory event queue. So
buffered typing in the 2-second flush window was dropped while the
session was still marked sealed. That quietly broke the "complete
authorship" guarantee.
- **Fix:** extended `POST /api/sessions/{id}/seal` to accept an optional
  `{events: [...]}` body. The `beforeunload` beacon now includes the
  drained queue, so the backend appends-then-seals atomically in one
  request.

**Bug B — transient backend hiccup on doc switch discards events.** `seal()`
always proceeded to clear `sessionId`, and the follow-up `detach()`
cleared the queue — even when `flush()` had failed and re-queued events.
- **Fix:** `seal()` retries flush up to 3× with backoff; `detach()`
  preserves `queue` so a doc switch during a brief network blip doesn't
  silently drop events.

Two new regression tests cover these in `test_provenance.py`.

### 2. Evaluation harness (regression gate, not benchmark)
`app/eval/` with:
- `samples/human.json` — 8 labelled human samples (public-domain Austen +
  Dickens excerpts plus synthetic casual-voice passages)
- `samples/ai.json` — 8 deliberately AI-voiced passages heavy on the
  usual "Moreover / Furthermore / it is important to note" markers
- `samples/preserve.json` — 5 citation/quote/code/LaTeX round-trip cases
- `runner.py` — loads the real detector, computes metrics, compares to
  `baseline.json`, with an `--update-baseline` flag for the first run
- `tests/test_eval.py` — pytest wrapper marked `@pytest.mark.eval`
- `pytest.ini` now excludes `eval`-marked tests from the default run so
  the fast suite stays fast; invoke the gate explicitly via `pytest -m eval`
- `.github/workflows/eval.yml` runs the gate on main-branch merges only
  (not every PR — the full detector load is ~30 s), with HF model cache

We deliberately **did not commit a baseline.json**. Generate it yourself
with `python -m app.eval.runner --update-baseline` on the machine you
consider "known-good" and commit the output.

Honest scope: this is a regression gate, not a frontier benchmark. The
samples are small and curated; we're catching regressions, not proving
absolute accuracy. Next iteration would pull from established benchmarks
like HC3 or GPABenchmark.

### 3. Playwright smoke tests
- `frontend/playwright.config.ts` — `webServer` boots BOTH a FakeRegistry-
  backed backend (via `run_test_server.py` — no HuggingFace, no Ollama)
  AND the Next.js dev server, then tears them down after the run
- `frontend/e2e/smoke.spec.ts` — two happy-path tests:
  1. Create project → create document → type → detect → humanize → verify
     output differs
  2. Writing Report modal opens and displays chain-integrity badge
- `run_test_server.py` is the backend counterpart — installs FakeRegistry
  and patches OllamaRewriter at module-import time so lifespan fires
  against fakes. Binds to port 8001 to coexist with a dev backend on 8000
- `.github/workflows/e2e.yml` wires Playwright into CI for every
  push + PR, uploads traces on failure

### What's intentionally deferred (again)
- **Real frontier benchmark** (HC3, etc.) — needs licence review + ~10×
  more samples
- **Authoring replay** (Grammarly-Authorship-style) — reconstruct document
  state at arbitrary timestamp from the event stream. Doable with the
  hash chain we already have, but scope-bounded to a future phase.
- **Code signing** — Azure Trusted Signing ($10/mo) eliminates SmartScreen.
  Still on the to-do list.
- **CUDA torch swap on install** — `build.ps1` ships CPU torch; users with
  NVIDIA GPUs swap manually per the README.

### Net numbers
- **69 tests** pass in 3.8 seconds offline (was 12 tests in Phase 0)
- **2 eval tests** skipped unless `-m eval`
- **2 Playwright specs** covering the critical user flows
- **3 CI workflows**: fast tests (every push), E2E (every push), eval (main only)

That's Phase 7.
