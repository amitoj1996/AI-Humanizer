from .classifier import AIClassifier
from .linguistic import LinguisticAnalyzer
from .perplexity import PerplexityAnalyzer


class EnsembleDetector:
    """Combines RoBERTa classifier, perplexity analysis, and linguistic
    features into a single AI-detection score."""

    def __init__(self):
        from ..config import CLASSIFIER_MODEL, PERPLEXITY_MODEL

        print(f"  Loading {CLASSIFIER_MODEL} classifier...")
        self.classifier = AIClassifier()

        print(f"  Loading {PERPLEXITY_MODEL} for perplexity analysis...")
        self.perplexity_analyzer = PerplexityAnalyzer()
        self.linguistic_analyzer = LinguisticAnalyzer()
        print("  All detector models loaded.")

    def quick_score(self, text: str) -> float:
        """Classifier-only AI score for ranking best-of-N candidates.

        Skips the perplexity forward pass (the dominant per-call cost —
        a Qwen-4B forward over the whole text plus one per sentence for
        burstiness) and the linguistic analysis. The classifier is a 33M
        LoRA'd e5-small that runs in ~15-25 ms on GPU, so a 3-candidate
        comparison drops from ~3-6 s of detector work to ~50-80 ms.

        We only need *relative* ordering to pick the best candidate;
        `detect()` runs the full ensemble once on the winner.
        """
        return self.classifier.predict_chunks(text)["ai_probability"]

    def quick_score_batch(self, texts: list[str]) -> list[float]:
        """Same as quick_score but batches N candidates into one padded
        forward pass. Assumes each text fits in the classifier window —
        safe for individual sentences; long paragraphs should use
        `quick_score()` which falls through to chunking.
        """
        if not texts:
            return []
        results = self.classifier.predict_batch(texts)
        return [r["ai_probability"] for r in results]

    def detect(self, text: str) -> dict:
        classifier_result = self.classifier.predict_chunks(text)
        perplexity_result = self.perplexity_analyzer.analyze(text)
        linguistic_result = self.linguistic_analyzer.analyze(text)

        # Weighted ensemble — e5-small-lora is near-SOTA on RAID so the
        # classifier now carries the dominant weight.
        weights = {"classifier": 0.50, "perplexity": 0.30, "linguistic": 0.20}

        ai_score = (
            weights["classifier"] * classifier_result["ai_probability"]
            + weights["perplexity"] * perplexity_result["combined_ai_signal"]
            + weights["linguistic"] * linguistic_result["ai_signal"]
        )

        if ai_score > 0.75:
            verdict = "AI-generated"
        elif ai_score > 0.55:
            verdict = "Likely AI-generated"
        elif ai_score > 0.40:
            verdict = "Mixed / Uncertain"
        elif ai_score > 0.25:
            verdict = "Likely human-written"
        else:
            verdict = "Human-written"

        return {
            "ai_score": round(ai_score, 4),
            "human_score": round(1 - ai_score, 4),
            "verdict": verdict,
            "breakdown": {
                "classifier": classifier_result,
                "perplexity": perplexity_result,
                "linguistic": linguistic_result,
            },
        }
