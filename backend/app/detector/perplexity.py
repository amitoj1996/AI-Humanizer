import re

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from ..config import PERPLEXITY_DEVICE, PERPLEXITY_MODEL


class PerplexityAnalyzer:
    """Compute perplexity and burstiness using a modern causal LM (Qwen2.5-0.5B).

    - Perplexity: how predictable the text is.  AI text → low perplexity.
    - Burstiness: variance of per-sentence perplexity.  AI text → low burstiness.
    """

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(
            PERPLEXITY_MODEL, trust_remote_code=True
        )
        # Use bf16 on CUDA (Ampere+ supported — e.g. 2xRTX 3070) for ~2x
        # throughput and half the VRAM versus fp32. bf16 is preferred
        # over fp16 for its wider dynamic range, which matters when
        # exponentiating loss to get perplexity. SDPA attention is the
        # PyTorch 2.x default for AutoModel and requires no extra deps.
        # On MPS/CPU we fall back to fp32 — bf16 perf is either unsupported
        # or slower.
        if PERPLEXITY_DEVICE.type == "cuda":
            dtype = torch.bfloat16
        else:
            dtype = torch.float32
        self.dtype = dtype
        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                PERPLEXITY_MODEL,
                trust_remote_code=True,
                dtype=dtype,
                attn_implementation="sdpa",
            ).to(PERPLEXITY_DEVICE)
        except (TypeError, ValueError):
            # Older transformers use `torch_dtype=`, and some models reject
            # an explicit `attn_implementation` — retry without those.
            self.model = AutoModelForCausalLM.from_pretrained(
                PERPLEXITY_MODEL, trust_remote_code=True, torch_dtype=dtype
            ).to(PERPLEXITY_DEVICE)
        self.model.eval()

    def compute_perplexity(self, text: str) -> float:
        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=1024
        ).to(PERPLEXITY_DEVICE)
        if inputs["input_ids"].shape[1] < 2:
            return 0.0
        with torch.no_grad():
            outputs = self.model(**inputs, labels=inputs["input_ids"])
        # Promote to fp32 before exp — bf16's 7-bit mantissa overflows
        # easily once the loss is above ~11, giving nonsense perplexities.
        return torch.exp(outputs.loss.float()).item()

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
