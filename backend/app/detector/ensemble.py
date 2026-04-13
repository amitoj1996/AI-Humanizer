from .classifier import AIClassifier
from .linguistic import LinguisticAnalyzer
from .perplexity import PerplexityAnalyzer


class EnsembleDetector:
    """Combines RoBERTa classifier, perplexity analysis, and linguistic
    features into a single AI-detection score."""

    def __init__(self):
        print("  Loading RoBERTa classifier...")
        self.classifier = AIClassifier()
        from ..config import PERPLEXITY_MODEL

        print(f"  Loading {PERPLEXITY_MODEL} for perplexity analysis...")
        self.perplexity_analyzer = PerplexityAnalyzer()
        self.linguistic_analyzer = LinguisticAnalyzer()
        print("  All detector models loaded.")

    def detect(self, text: str) -> dict:
        classifier_result = self.classifier.predict_chunks(text)
        perplexity_result = self.perplexity_analyzer.analyze(text)
        linguistic_result = self.linguistic_analyzer.analyze(text)

        # Weighted ensemble — perplexity & linguistic signals are more
        # reliable for modern AI text than the RoBERTa classifier (GPT-2 era).
        weights = {"classifier": 0.30, "perplexity": 0.35, "linguistic": 0.35}

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
