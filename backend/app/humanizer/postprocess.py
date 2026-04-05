import random
import re

import nltk

# Ensure NLTK data is available
for pkg in ("wordnet", "punkt_tab", "averaged_perceptron_tagger"):
    try:
        nltk.data.find(f"corpora/{pkg}" if pkg == "wordnet" else f"tokenizers/{pkg}" if "punkt" in pkg else f"taggers/{pkg}")
    except LookupError:
        nltk.download(pkg, quiet=True)


class TextPostProcessor:
    """Rule-based transformations that disrupt the statistical fingerprints
    AI detectors rely on: predictable transitions, lack of contractions,
    uniform sentence structure."""

    TRANSITION_MAP = {
        r"\bMoreover\b": ["Plus", "On top of that", "And", "Also"],
        r"\bFurthermore\b": ["Plus", "And", "What's more", "Also"],
        r"\bAdditionally\b": ["Also", "On top of that", "Plus", "And"],
        r"\bIn conclusion\b": ["All in all", "So basically", "To wrap up", "Bottom line"],
        r"\bIt is important to note that\b": ["Worth noting —", "Thing is,", "Keep in mind,"],
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

    def process(self, text: str, intensity: float = 0.5) -> str:
        text = self._replace_transitions(text, intensity)
        text = self._add_contractions(text, intensity)
        text = self._vary_sentences(text, intensity)
        return text

    def _replace_transitions(self, text: str, intensity: float) -> str:
        for pattern, replacements in self.TRANSITION_MAP.items():
            if random.random() < intensity:
                text = re.sub(pattern, random.choice(replacements), text, count=1)
        return text

    def _add_contractions(self, text: str, intensity: float) -> str:
        for pattern, contraction in self.CONTRACTIONS.items():
            if random.random() < intensity:
                text = re.sub(pattern, contraction, text, flags=re.IGNORECASE)
        return text

    def _vary_sentences(self, text: str, intensity: float) -> str:
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
            if len(words) > 25 and random.random() < intensity * 0.3:
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
