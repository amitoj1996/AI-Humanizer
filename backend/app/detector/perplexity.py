import re

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from ..config import DEVICE, PERPLEXITY_MODEL


class PerplexityAnalyzer:
    """Compute perplexity and burstiness using a modern causal LM (Qwen2.5-0.5B).

    - Perplexity: how predictable the text is.  AI text → low perplexity.
    - Burstiness: variance of per-sentence perplexity.  AI text → low burstiness.
    """

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(
            PERPLEXITY_MODEL, trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            PERPLEXITY_MODEL, trust_remote_code=True, torch_dtype=torch.float32
        ).to(DEVICE)
        self.model.eval()

    def compute_perplexity(self, text: str) -> float:
        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=1024
        ).to(DEVICE)
        if inputs["input_ids"].shape[1] < 2:
            return 0.0
        with torch.no_grad():
            outputs = self.model(**inputs, labels=inputs["input_ids"])
        return torch.exp(outputs.loss).item()

    def compute_burstiness(self, text: str) -> float:
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip().split()) > 3]

        if len(sentences) < 3:
            return 0.0

        perplexities = []
        for sent in sentences:
            ppl = self.compute_perplexity(sent)
            if np.isfinite(ppl) and ppl > 0:
                perplexities.append(ppl)

        if len(perplexities) < 3:
            return 0.0

        mean_ppl = float(np.mean(perplexities))
        std_ppl = float(np.std(perplexities))
        return std_ppl / (mean_ppl + 1e-8)

    def analyze(self, text: str) -> dict:
        perplexity = self.compute_perplexity(text)
        burstiness = self.compute_burstiness(text)

        # Normalize to 0-1 signals (lower values = more AI-like)
        ppl_score = min(1.0, perplexity / 100.0)
        burst_score = min(1.0, burstiness / 0.5)

        ai_signal = 1.0 - (0.5 * ppl_score + 0.5 * burst_score)

        return {
            "perplexity": round(perplexity, 2),
            "burstiness": round(burstiness, 4),
            "perplexity_ai_signal": round(1.0 - ppl_score, 4),
            "burstiness_ai_signal": round(1.0 - burst_score, 4),
            "combined_ai_signal": round(ai_signal, 4),
        }
