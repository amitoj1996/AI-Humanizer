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

# Detection models
CLASSIFIER_MODEL = "roberta-base-openai-detector"
PERPLEXITY_MODEL = "Qwen/Qwen3.5-0.8B"

# Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3.5:4b"

# Detection thresholds
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
