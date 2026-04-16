import os

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ..config import CLASSIFIER_DEVICE, CLASSIFIER_MODEL


class AIClassifier:
    """RoBERTa-based binary classifier for AI-generated text detection.

    Exposes `predict_batch()` so callers scoring N candidates run a single
    padded forward pass instead of N. The tokenizer pads to the longest
    input in each batch, and we cap `max_length=512` so padding is bounded.
    """

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(CLASSIFIER_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            CLASSIFIER_MODEL
        ).to(CLASSIFIER_DEVICE)
        self.model.eval()

        # Opt-in compile — torch.compile on the classifier gives a 20-40%
        # speedup on Ampere+ but adds a multi-second compile on first call.
        # Off by default so first-request latency stays low.
        if os.environ.get("AI_HUMANIZER_COMPILE", "0") == "1" and CLASSIFIER_DEVICE.type == "cuda":
            try:
                self.model = torch.compile(self.model, mode="reduce-overhead")
            except Exception:
                pass

    def predict(self, text: str) -> dict:
        return self.predict_batch([text])[0]

    def predict_batch(self, texts: list[str]) -> list[dict]:
        """Score N texts in a single padded forward pass."""
        if not texts:
            return []
        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(CLASSIFIER_DEVICE)

        # inference_mode is strictly faster than no_grad on hot inference
        # paths — it also disables view tracking and version-counter bumps
        # that no_grad still pays for. No correctness change.
        with torch.inference_mode():
            outputs = self.model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1)
        return [
            {
                "human_probability": round(probs[i, 0].item(), 4),
                "ai_probability": round(probs[i, 1].item(), 4),
            }
            for i in range(probs.shape[0])
        ]

    def predict_chunks(self, text: str, chunk_size: int = 512) -> dict:
        """Split long texts into overlapping chunks and average predictions."""
        tokens = self.tokenizer.encode(text)
        if len(tokens) <= chunk_size:
            return self.predict(text)

        overlap = 50
        chunks = []
        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i : i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens, skip_special_tokens=True)
            chunks.append(chunk_text)

        # Single batched forward over all chunks instead of one call each.
        results = self.predict_batch(chunks)
        avg_ai = sum(r["ai_probability"] for r in results) / len(results)
        avg_human = sum(r["human_probability"] for r in results) / len(results)

        return {
            "human_probability": round(avg_human, 4),
            "ai_probability": round(avg_ai, 4),
            "chunks_analyzed": len(chunks),
        }
