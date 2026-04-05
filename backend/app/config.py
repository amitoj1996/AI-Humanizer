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
