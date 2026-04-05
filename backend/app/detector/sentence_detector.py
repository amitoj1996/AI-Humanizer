import re

from .ensemble import EnsembleDetector


class SentenceDetector:
    """Per-sentence AI detection — powers the heatmap UI.

    Splits text into sentences, scores each one individually, and
    returns a list so the frontend can highlight flagged regions.
    """

    MIN_WORDS = 6  # sentences shorter than this lack statistical signal

    def __init__(self, detector: EnsembleDetector):
        self.detector = detector

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text)
        return [p.strip() for p in parts if p.strip()]

    def detect_sentences(self, text: str) -> dict:
        sentences = self.split_sentences(text)

        results: list[dict] = []
        scored_ai_total = 0.0
        scored_count = 0

        for sent in sentences:
            word_count = len(sent.split())
            if word_count < self.MIN_WORDS:
                results.append(
                    {
                        "sentence": sent,
                        "ai_score": None,
                        "verdict": "Too short to score",
                        "word_count": word_count,
                    }
                )
                continue

            detection = self.detector.detect(sent)
            ai_score = detection["ai_score"]
            scored_ai_total += ai_score
            scored_count += 1

            if ai_score > 0.65:
                verdict = "AI-generated"
            elif ai_score > 0.40:
                verdict = "Suspicious"
            else:
                verdict = "Human-like"

            results.append(
                {
                    "sentence": sent,
                    "ai_score": round(ai_score, 4),
                    "verdict": verdict,
                    "word_count": word_count,
                }
            )

        avg_ai = round(scored_ai_total / scored_count, 4) if scored_count else 0.0

        # Full-text detection for the overall score
        overall = self.detector.detect(text)

        return {
            "overall": overall,
            "average_sentence_ai": avg_ai,
            "sentences": results,
            "total_sentences": len(sentences),
            "scored_sentences": scored_count,
        }
