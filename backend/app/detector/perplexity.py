import re

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from ..config import PERPLEXITY_DEVICE, PERPLEXITY_MODEL, PERPLEXITY_QUANTIZE


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

        # Optional bitsandbytes quantisation — lets users fit larger
        # perplexity models (e.g. Qwen3.5-4B at ~2.5 GB in 4bit) on an
        # 8 GB card. quantised models must be device-placed via
        # device_map; .to() is not supported on bnb weights.
        quant_config = None
        if PERPLEXITY_QUANTIZE in ("4bit", "8bit"):
            try:
                from transformers import BitsAndBytesConfig

                if PERPLEXITY_QUANTIZE == "4bit":
                    quant_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_compute_dtype=dtype,
                    )
                else:
                    quant_config = BitsAndBytesConfig(load_in_8bit=True)
            except ImportError:
                print(
                    "  WARNING: AI_HUMANIZER_QUANTIZE set but bitsandbytes "
                    "is not installed; falling back to bf16."
                )

        load_kwargs: dict = {"trust_remote_code": True}
        if quant_config is not None:
            load_kwargs["quantization_config"] = quant_config
            load_kwargs["device_map"] = {"": PERPLEXITY_DEVICE}
        else:
            load_kwargs["dtype"] = dtype
            load_kwargs["attn_implementation"] = "sdpa"

        try:
            self.model = AutoModelForCausalLM.from_pretrained(
                PERPLEXITY_MODEL, **load_kwargs
            )
        except (TypeError, ValueError):
            # Older transformers use `torch_dtype=` and some models
            # reject `attn_implementation`; retry with the minimal set.
            fallback = {"trust_remote_code": True, "torch_dtype": dtype}
            if quant_config is not None:
                fallback["quantization_config"] = quant_config
                fallback["device_map"] = {"": PERPLEXITY_DEVICE}
            self.model = AutoModelForCausalLM.from_pretrained(
                PERPLEXITY_MODEL, **fallback
            )

        if quant_config is None:
            self.model = self.model.to(PERPLEXITY_DEVICE)
        self.model.eval()

    def compute_perplexity(self, text: str) -> float:
        inputs = self.tokenizer(
            text, return_tensors="pt", truncation=True, max_length=1024
        ).to(PERPLEXITY_DEVICE)
        if inputs["input_ids"].shape[1] < 2:
            return 0.0
        # inference_mode is strictly faster than no_grad on hot inference
        # paths (PyTorch docs). Same correctness, fewer autograd hooks.
        with torch.inference_mode():
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
