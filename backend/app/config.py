"""Runtime configuration.

Model picks verified against official releases as of April 2026.  Override
any of these via environment variables — the defaults target a
single 8 GB GPU (e.g. RTX 3070), which is the most common "capable but not
huge" tier right now.
"""
import os
import sys
from pathlib import Path

import torch


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _resolve_device(env_var: str) -> torch.device:
    """Pick a device from an env var (e.g. 'cuda:1', 'cpu') or fall back.

    Multi-GPU hosts (e.g. 2x RTX 3070) can spread load across cards —
    classifier on cuda:1, perplexity LM on cuda:0, Ollama across both —
    by setting AI_HUMANIZER_CLASSIFIER_DEVICE / _PERPLEXITY_DEVICE.
    """
    spec = os.environ.get(env_var)
    if not spec:
        return get_device()
    try:
        return torch.device(spec)
    except RuntimeError:
        return get_device()


DEVICE = get_device()
# Per-module device pins — default to the primary device; override per
# model to spread GPU load on multi-GPU hosts.
CLASSIFIER_DEVICE = _resolve_device("AI_HUMANIZER_CLASSIFIER_DEVICE")
PERPLEXITY_DEVICE = _resolve_device("AI_HUMANIZER_PERPLEXITY_DEVICE")

# ---------------------------------------------------------------------------
# Detection models
# ---------------------------------------------------------------------------
# e5-small fine-tuned with LoRA for AI-generated text detection.
# Near-SOTA on the RAID benchmark, 33M params (~130MB), ~4x faster than the
# legacy roberta-base-openai-detector (which was trained on GPT-2 outputs
# and degrades badly on modern LLM text).
CLASSIFIER_MODEL = os.environ.get(
    "AI_HUMANIZER_CLASSIFIER_MODEL", "MayZhou/e5-small-lora-ai-generated-detector"
)

# Perplexity / burstiness scoring via a small modern base LM.
# Qwen 3.5-4B-Base is the current official small-base release; its
# tokenizer and natural-language fluency are the best in its class.
# Tune down to Qwen/Qwen3.5-0.8B (or similar) on CPU-only boxes where
# 4 B forward passes per sentence become the bottleneck.
PERPLEXITY_MODEL = os.environ.get(
    "AI_HUMANIZER_PERPLEXITY_MODEL", "Qwen/Qwen3.5-4B-Base"
)

# ---------------------------------------------------------------------------
# Ollama configuration
# ---------------------------------------------------------------------------
# Default rewriter: qwen3.5:9b (6.6 GB, Q4_K_M) — fits on a single 8 GB GPU
# which Ollama prefers over multi-GPU splitting.
#
# Profile suggestions (switch via the UI model selector or env var):
#   Fast    : qwen3.5:4b     (3.4 GB, snappier UI, concurrent detection OK)
#   Reasoning: deepseek-r1:8b (5.2 GB, better analysis, style can drift)
#   Quality : mistral-small3.2:24b (15 GB, will span both GPUs — experimental)
#   Avoid   : llama4 (67 GB smallest official tag — too big)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("AI_HUMANIZER_OLLAMA_MODEL", "qwen3.5:9b")

# How long Ollama keeps a model resident in VRAM after the last request.
# Defaults are per Ollama docs (5m) but that causes cold starts when we
# rotate between qwen and gemma in sentence mode. "30m" is a good
# interactive default; "-1" keeps models loaded indefinitely (dedicated
# server); "0" unloads immediately after every request.
OLLAMA_KEEP_ALIVE = os.environ.get("AI_HUMANIZER_OLLAMA_KEEP_ALIVE", "30m")

# Candidate models for diverse best-of-N in sentence mode.  Different
# tokenizers and training distributions produce candidates with distinct
# statistical fingerprints — a single detector is much less likely to flag
# candidates drawn from unrelated base models than N candidates from one.
# GPTZero (Apr 2026) ships paraphraser-fingerprint detectors specifically
# keyed to single-model humanizers, so diversity matters for evasion.
#
# Default assumes Ollama has qwen3.5:9b + gemma4 pulled.  On a 16 GB GPU
# pool (e.g. 2x RTX 3070) Ollama swaps them in/out as needed.
# Override with a comma-separated list:
#   AI_HUMANIZER_CANDIDATE_MODELS=qwen3.5:9b,gemma4:latest,deepseek-r1:8b
_default_candidates = f"{OLLAMA_MODEL},gemma4:latest"
OLLAMA_CANDIDATE_MODELS = [
    m.strip()
    for m in os.environ.get(
        "AI_HUMANIZER_CANDIDATE_MODELS", _default_candidates
    ).split(",")
    if m.strip()
]

# Max concurrent Ollama rewrite requests per sentence. Default matches
# the number of distinct candidate models because Ollama serializes
# requests to the same model by default (unless OLLAMA_NUM_PARALLEL > 1
# is set on the server). On a dual-3070 box with qwen3.5:9b + gemma4,
# 2 is safely concurrent; set OLLAMA_NUM_PARALLEL=2 and raise this if
# you want candidates_per_sentence fanout too.
MAX_CONCURRENT_REWRITES = int(
    os.environ.get(
        "AI_HUMANIZER_MAX_CONCURRENT_REWRITES", str(len(OLLAMA_CANDIDATE_MODELS))
    )
)

# Minimum cosine similarity a sentence-mode candidate must have vs. the
# original to be eligible.  Protects against semantic drift when the
# rewriter drops a low-AI-score but meaning-changed candidate.
MIN_SEMANTIC_SIMILARITY = float(
    os.environ.get("AI_HUMANIZER_MIN_SIMILARITY", "0.82")
)

# ---------------------------------------------------------------------------
# Detection thresholds
# ---------------------------------------------------------------------------
AI_THRESHOLD = 0.65
HUMAN_THRESHOLD = 0.35


# ---------------------------------------------------------------------------
# Application data directory (SQLite DB lives here)
# ---------------------------------------------------------------------------
def _default_app_data_dir() -> Path:
    """Platform-appropriate app data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AIHumanizer"
    if sys.platform == "win32":
        appdata = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(appdata) / "AIHumanizer"
    # Linux / other
    xdg = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(xdg) / "aihumanizer"


APP_DATA_DIR = Path(os.environ.get("AI_HUMANIZER_DATA_DIR", _default_app_data_dir()))
DB_PATH = Path(os.environ.get("AI_HUMANIZER_DB_PATH", APP_DATA_DIR / "aih.db"))
