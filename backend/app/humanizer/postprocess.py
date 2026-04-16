import random
import re


class TextPostProcessor:
    """Rule-based transformations that disrupt the statistical fingerprints
    AI detectors rely on: predictable transitions, lack of contractions,
    uniform sentence structure.

    Non-determinism is seedable — pass a `seed` to `process()` to make
    evaluation runs reproducible. Without a seed we draw fresh randomness
    from the global state so production output still varies naturally.
    """

    # Em-dash-introducing replacements removed deliberately: em-dashes
    # (U+2014) are one of the strongest unigram signals modern detectors
    # key on, so introducing them via postprocess defeats the purpose.
    TRANSITION_MAP = {
        r"\bMoreover\b": ["Plus", "On top of that", "And", "Also"],
        r"\bFurthermore\b": ["Plus", "And", "What's more", "Also"],
        r"\bAdditionally\b": ["Also", "On top of that", "Plus", "And"],
        r"\bIn conclusion\b": ["All in all", "So basically", "To wrap up", "Bottom line"],
        r"\bIt is important to note that\b": ["Worth noting,", "Thing is,", "Keep in mind,"],
        r"\bIt's worth noting that\b": ["Interestingly,", "Thing is,"],
        r"\bOn the other hand\b": ["Then again", "But", "That said", "Flip side though"],
        r"\bIn summary\b": ["So basically", "Long story short", "All in all"],
        r"\bConsequently\b": ["So", "Because of that", "As a result"],
        r"\bNevertheless\b": ["Still", "But", "Even so", "That said"],
        r"\bHowever\b": ["But", "That said", "Still", "Though"],
        r"\bTherefore\b": ["So", "That's why", "Because of this"],
        r"\bUtilize\b": ["Use", "Work with"],
        r"\butilize\b": ["use", "work with"],
        r"\bdelve\b": ["dig into", "explore", "look at", "get into"],
        r"\bDelve\b": ["Dig into", "Explore", "Look at", "Get into"],
        r"\bLeverage\b": ["Use", "Take advantage of"],
        r"\bleverage\b": ["use", "take advantage of"],
        r"\bFacilitate\b": ["Help", "Make easier", "Enable"],
        r"\bfacilitate\b": ["help", "make easier", "enable"],
        r"\bEnhance\b": ["Improve", "Boost", "Step up"],
        r"\benhance\b": ["improve", "boost", "step up"],
    }

    CONTRACTIONS = {
        r"\bdo not\b": "don't",
        r"\bcannot\b": "can't",
        r"\bwill not\b": "won't",
        r"\bshould not\b": "shouldn't",
        r"\bwould not\b": "wouldn't",
        r"\bcould not\b": "couldn't",
        r"\bis not\b": "isn't",
        r"\bare not\b": "aren't",
        r"\bwas not\b": "wasn't",
        r"\bwere not\b": "weren't",
        r"\bhave not\b": "haven't",
        r"\bhas not\b": "hasn't",
        r"\bhad not\b": "hadn't",
        r"\bdoes not\b": "doesn't",
        r"\bthey are\b": "they're",
        r"\bwe are\b": "we're",
        r"\byou are\b": "you're",
        r"\bit is\b": "it's",
        r"\bthat is\b": "that's",
        r"\bI am\b": "I'm",
        r"\bI have\b": "I've",
        r"\bI will\b": "I'll",
        r"\bI would\b": "I'd",
    }

    # Double-quoted spans (straight + curly) we must not mutate. Single
    # quotes are too noisy (contractions, possessives) to safely skip.
    _QUOTE_SPAN = re.compile(r'"[^"\n]+?"|\u201c[^\u201d\n]+?\u201d')

    def process(self, text: str, intensity: float = 0.5, seed: int | None = None) -> str:
        rng = random.Random(seed) if seed is not None else random
        text = self._replace_transitions(text, intensity, rng)
        text = self._add_contractions(text, intensity, rng)
        text = self._vary_sentences(text, intensity, rng)
        text = self._strip_em_dashes(text)
        return text

    def _replace_transitions(self, text: str, intensity: float, rng) -> str:
        for pattern, replacements in self.TRANSITION_MAP.items():
            if rng.random() < intensity:
                text = re.sub(pattern, rng.choice(replacements), text, count=1)
        return text

    def _add_contractions(self, text: str, intensity: float, rng) -> str:
        """Contract outside quoted spans only.

        Mutating inside quotes changes what a source allegedly said, which
        is a quality bug; we split on quote boundaries, contract the
        non-quote segments, and re-stitch.
        """
        parts = []
        cursor = 0
        for m in self._QUOTE_SPAN.finditer(text):
            parts.append(("text", text[cursor : m.start()]))
            parts.append(("quote", m.group()))
            cursor = m.end()
        parts.append(("text", text[cursor:]))

        out = []
        for kind, chunk in parts:
            if kind == "quote":
                out.append(chunk)
                continue
            for pattern, contraction in self.CONTRACTIONS.items():
                if rng.random() < intensity:
                    chunk = re.sub(pattern, contraction, chunk, flags=re.IGNORECASE)
            out.append(chunk)
        return "".join(out)

    def _vary_sentences(self, text: str, intensity: float, rng) -> str:
        if intensity < 0.3:
            return text

        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) < 4:
            return text

        result = []
        conjunctions = {"and", "but", "so", "which", "because", "while", "although"}

        for sent in sentences:
            words = sent.split()
            # Occasionally split very long sentences
            if len(words) > 25 and rng.random() < intensity * 0.3:
                mid = len(words) // 2
                for j in range(max(0, mid - 3), min(len(words), mid + 4)):
                    if words[j].lower() in conjunctions:
                        first = " ".join(words[:j])
                        second = " ".join(words[j:])
                        second = second[0].upper() + second[1:] if len(second) > 1 else second
                        if not first.rstrip().endswith("."):
                            first = first.rstrip() + "."
                        sent = f"{first} {second}"
                        break
            result.append(sent)

        return " ".join(result)

    @staticmethod
    def _strip_em_dashes(text: str) -> str:
        """Remove em-dashes (U+2014) the rewriter may have slipped in.
        Em-dashes are one of the strongest AI tells in current detectors.

        Absorb surrounding whitespace so `a — b` becomes `a, b` (not
        `a ,  b`), and collapse accidental `, ,` runs.

        En-dashes (U+2013) are intentionally NOT touched: they are the
        correct typography for numeric ranges (10–12%, pp. 3–5,
        2024–2025) and replacing them with commas would corrupt meaning.
        """
        text = re.sub(r"\s*\u2014\s*", ", ", text)
        text = re.sub(r",\s*,", ",", text)
        return text
