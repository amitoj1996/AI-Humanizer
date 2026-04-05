import math
import re


class LinguisticAnalyzer:
    """Rule-based linguistic feature analysis for AI text detection.

    Examines sentence-length variance, vocabulary richness, AI marker words,
    and contraction usage — all strong stylistic signals.
    """

    AI_MARKERS = [
        "moreover",
        "furthermore",
        "additionally",
        "in conclusion",
        "it is important to note",
        "it's worth noting",
        "it is worth mentioning",
        "in today's world",
        "in the realm of",
        "plays a crucial role",
        "it is essential",
        "on the other hand",
        "in summary",
        "delve",
        "crucial",
        "comprehensive",
        "multifaceted",
        "landscape",
        "paradigm",
        "leveraging",
        "utilizing",
        "streamline",
        "foster",
        "facilitate",
        "enhance",
        "navigate",
        "pivotal",
        "nuanced",
        "robust",
        "underscores",
        "realm",
        "tapestry",
        "bustling",
        "testament",
        "intricacies",
    ]

    def analyze(self, text: str) -> dict:
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip()]
        words = re.findall(r"\b\w+\b", text.lower())

        if not words or not sentences:
            return {"ai_signal": 0.5}

        # --- Sentence length variance ---
        sent_lengths = [len(s.split()) for s in sentences]
        mean_len = sum(sent_lengths) / len(sent_lengths)
        variance = sum((l - mean_len) ** 2 for l in sent_lengths) / len(sent_lengths)
        cv = math.sqrt(variance) / (mean_len + 1e-8)  # coefficient of variation

        # --- Vocabulary richness (Type-Token Ratio) ---
        ttr = len(set(words)) / len(words)

        # --- AI marker density (per 100 words) ---
        text_lower = text.lower()
        marker_count = sum(1 for m in self.AI_MARKERS if m in text_lower)
        marker_density = marker_count / (len(words) / 100)

        # --- Contraction usage (per 100 words) ---
        contractions = len(
            re.findall(
                r"\b\w+n't\b|\b\w+'re\b|\b\w+'ve\b|\b\w+'ll\b|\b\w+'d\b|\b\w+'s\b|\bI'm\b",
                text,
            )
        )
        contraction_rate = contractions / (len(words) / 100)

        # --- Score components (higher = more AI-like) ---
        cv_score = max(0.0, 1.0 - cv / 0.8)  # humans have higher CV
        ttr_score = max(0.0, 1.0 - ttr / 0.7)  # humans have higher TTR
        marker_score = min(1.0, marker_density / 3.0)  # AI uses more markers
        contraction_score = max(
            0.0, 1.0 - contraction_rate / 2.0
        )  # humans use more contractions

        ai_signal = (
            0.25 * cv_score
            + 0.25 * ttr_score
            + 0.30 * marker_score
            + 0.20 * contraction_score
        )

        return {
            "sentence_length_cv": round(cv, 4),
            "type_token_ratio": round(ttr, 4),
            "ai_marker_density": round(marker_density, 4),
            "contraction_rate": round(contraction_rate, 4),
            "ai_signal": round(ai_signal, 4),
            "details": {
                "avg_sentence_length": round(mean_len, 1),
                "sentence_count": len(sentences),
                "word_count": len(words),
                "unique_words": len(set(words)),
                "ai_markers_found": marker_count,
                "contractions_found": contractions,
            },
        }
