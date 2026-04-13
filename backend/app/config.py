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


DEVICE = get_device()

# ---------------------------------------------------------------------------
# Detection models
# ---------------------------------------------------------------------------
# RoBERTa fine-tuned binary classifier — lightweight, fast, runs on any device.
CLASSIFIER_MODEL = os.environ.get(
    "AI_HUMANIZER_CLASSIFIER_MODEL", "roberta-base-openai-detector"
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
