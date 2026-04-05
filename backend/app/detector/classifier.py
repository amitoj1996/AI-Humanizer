import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ..config import DEVICE, CLASSIFIER_MODEL


class AIClassifier:
    """RoBERTa-based binary classifier for AI-generated text detection."""

    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(CLASSIFIER_MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            CLASSIFIER_MODEL
        ).to(DEVICE)
        self.model.eval()

    def predict(self, text: str) -> dict:
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(DEVICE)

        with torch.no_grad():
            outputs = self.model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1)[0]

        # The model's id2label says 0=Real, 1=Fake but empirical testing
        # shows the labels are inverted in practice — swap them.
        return {
            "human_probability": round(probs[1].item(), 4),
            "ai_probability": round(probs[0].item(), 4),
        }

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

        results = [self.predict(chunk) for chunk in chunks]
        avg_ai = sum(r["ai_probability"] for r in results) / len(results)
        avg_human = sum(r["human_probability"] for r in results) / len(results)

        return {
            "human_probability": round(avg_human, 4),
            "ai_probability": round(avg_ai, 4),
            "chunks_analyzed": len(chunks),
        }
