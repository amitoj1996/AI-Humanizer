import math
import re


class LinguisticAnalyzer:
    """Rule-based linguistic feature analysis for AI text detection.

    Examines sentence-length variance, vocabulary richness, AI marker words,
    contraction usage, em-dash usage, and punctuation distribution.

    Markers are split into two groups to control false positives:

    - `AI_PHRASES`: multi-word sequences that are rare in human prose but
      common in LLM output. These count at full weight.
    - `AI_WEAK_MARKERS`: single words (delve, crucial, robust, ...) that
      appear naturally in human writing too. These only count if the text
      is ALSO showing other AI signals — i.e. they act as amplifiers, not
      standalone evidence. Prevents flagging human text that happens to
      use one of these words in isolation.
    """

    AI_PHRASES = [
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
        "to put it simply",
        "when it comes to",
        "a testament to",
        "a tapestry of",
        "navigate the complexities",
    ]

    AI_WEAK_MARKERS = [
        "moreover",
        "furthermore",
        "additionally",
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
        "pivotal",
        "nuanced",
        "robust",
        "underscores",
        "realm",
        "tapestry",
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
        # Phrases count at full weight; weak unigrams count at half and
        # only survive if other signals also fire.
        text_lower = text.lower()
        phrase_count = sum(1 for m in self.AI_PHRASES if m in text_lower)
        weak_count = sum(1 for m in self.AI_WEAK_MARKERS if m in text_lower)
        per_100 = max(1.0, len(words) / 100)
        phrase_density = phrase_count / per_100
        weak_density = weak_count / per_100

        # --- Contraction usage (per 100 words) ---
        contractions = len(
            re.findall(
                r"\b\w+n't\b|\b\w+'re\b|\b\w+'ve\b|\b\w+'ll\b|\b\w+'d\b|\b\w+'s\b|\bI'm\b",
                text,
            )
        )
        contraction_rate = contractions / per_100

        # --- Em-dash density (per 100 words) ---
        # Em-dashes (U+2014) are one of the strongest modern AI tells;
        # human writers rarely use more than one per page.
        em_dash_count = text.count("\u2014") + text.count("\u2013")
        em_dash_density = em_dash_count / per_100

        # --- Score components (higher = more AI-like) ---
        cv_score = max(0.0, 1.0 - cv / 0.8)  # humans have higher CV
        ttr_score = max(0.0, 1.0 - ttr / 0.7)  # humans have higher TTR
        phrase_score = min(1.0, phrase_density / 2.0)
        # Weak markers alone shouldn't convict — attenuate unless phrases
        # or em-dashes are also firing.
        amp = 1.0 if (phrase_score > 0.1 or em_dash_density > 0.5) else 0.4
        weak_score = min(1.0, weak_density / 3.0) * amp
        marker_score = min(1.0, 0.6 * phrase_score + 0.4 * weak_score)
        contraction_score = max(
            0.0, 1.0 - contraction_rate / 2.0
        )  # humans use more contractions
        em_dash_score = min(1.0, em_dash_density / 1.0)

        ai_signal = (
            0.20 * cv_score
            + 0.20 * ttr_score
            + 0.25 * marker_score
            + 0.15 * contraction_score
            + 0.20 * em_dash_score
        )

        total_markers = phrase_count + weak_count
        total_density = phrase_density + weak_density
        return {
            "sentence_length_cv": round(cv, 4),
            "type_token_ratio": round(ttr, 4),
            # Combined density is preserved for the existing frontend /
            # test contract; the new split fields are additive.
            "ai_marker_density": round(total_density, 4),
            "ai_phrase_density": round(phrase_density, 4),
            "ai_weak_marker_density": round(weak_density, 4),
            "contraction_rate": round(contraction_rate, 4),
            "em_dash_density": round(em_dash_density, 4),
            "ai_signal": round(ai_signal, 4),
            "details": {
                "avg_sentence_length": round(mean_len, 1),
                "sentence_count": len(sentences),
                "word_count": len(words),
                "unique_words": len(set(words)),
                "ai_markers_found": total_markers,
                "ai_phrases_found": phrase_count,
                "ai_weak_markers_found": weak_count,
                "contractions_found": contractions,
                "em_dashes_found": em_dash_count,
            },
        }
