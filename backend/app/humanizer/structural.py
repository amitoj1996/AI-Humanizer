import random
import re


class StructuralRewriter:
    """Deep structural transformations that go beyond word-level changes.

    - Clause reordering (move subordinate clauses)
    - Sentence splitting / merging
    - Active ↔ passive hints (via markers the LLM can pick up)
    - Paragraph rhythm variation
    """

    SUBORDINATE_STARTERS = [
        "because",
        "since",
        "although",
        "while",
        "when",
        "if",
        "unless",
        "even though",
        "as long as",
        "whereas",
        "after",
        "before",
        "until",
    ]

    def rewrite(self, text: str, intensity: float = 0.5) -> str:
        text = self._reorder_clauses(text, intensity)
        text = self._split_long_sentences(text, intensity)
        text = self._merge_short_sentences(text, intensity)
        text = self._vary_paragraph_rhythm(text, intensity)
        return text

    def _reorder_clauses(self, text: str, intensity: float) -> str:
        """Move subordinate clauses from the end to the front (or vice versa)."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        result = []
        for sent in sentences:
            if random.random() > intensity * 0.4:
                result.append(sent)
                continue

            # Check for mid-sentence subordinate clause
            for starter in self.SUBORDINATE_STARTERS:
                pattern = rf",\s+({starter}\s+.+?)([.!?])$"
                match = re.search(pattern, sent, re.IGNORECASE)
                if match:
                    clause = match.group(1).strip()
                    punct = match.group(2)
                    main = sent[: match.start()].strip()
                    # Move clause to front
                    clause_cap = clause[0].upper() + clause[1:]
                    main_lower = main[0].lower() + main[1:] if main else main
                    sent = f"{clause_cap}, {main_lower}{punct}"
                    break

            result.append(sent)
        return " ".join(result)

    def _split_long_sentences(self, text: str, intensity: float) -> str:
        """Split compound sentences at conjunctions."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        result = []
        split_words = {"and", "but", "so", "yet", "however", "therefore"}

        for sent in sentences:
            words = sent.split()
            if len(words) < 20 or random.random() > intensity * 0.4:
                result.append(sent)
                continue

            # Find a good split point
            mid = len(words) // 2
            best_j = None
            best_dist = float("inf")
            for j in range(max(5, mid - 8), min(len(words) - 5, mid + 8)):
                if words[j].lower().strip(",") in split_words:
                    dist = abs(j - mid)
                    if dist < best_dist:
                        best_dist = dist
                        best_j = j

            if best_j is not None:
                first = " ".join(words[:best_j]).rstrip(",")
                if not first.endswith((".", "!", "?")):
                    first += "."
                second = " ".join(words[best_j:])
                # Capitalize and clean
                conj = words[best_j].lower().strip(",")
                if conj in ("and", "so", "yet"):
                    second = second[0].upper() + second[1:] if second else second
                else:
                    second = second[0].upper() + second[1:] if second else second
                result.append(f"{first} {second}")
            else:
                result.append(sent)

        return " ".join(result)

    def _merge_short_sentences(self, text: str, intensity: float) -> str:
        """Merge consecutive very short sentences."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        if len(sentences) < 3:
            return text

        result = []
        i = 0
        # No em-dashes here — they are a strong AI-detection unigram as
        # of 2025-2026 and would defeat the rest of the humanization pass.
        connectors = ["and", "plus", "which means", "so", "because"]

        while i < len(sentences):
            sent = sentences[i]
            words = sent.split()

            if (
                i + 1 < len(sentences)
                and len(words) < 8
                and len(sentences[i + 1].split()) < 8
                and random.random() < intensity * 0.3
            ):
                next_sent = sentences[i + 1]
                # Remove period from first, lowercase second
                first = sent.rstrip(".!?")
                second = next_sent[0].lower() + next_sent[1:] if next_sent else next_sent
                connector = random.choice(connectors)
                merged = f"{first} {connector} {second}"
                result.append(merged)
                i += 2
            else:
                result.append(sent)
                i += 1

        return " ".join(result)

    def _vary_paragraph_rhythm(self, text: str, intensity: float) -> str:
        """Redistribute sentences across paragraphs for varied rhythm."""
        paragraphs = text.split("\n\n")
        if len(paragraphs) < 2 or intensity < 0.4:
            return text

        # Collect all sentences
        all_sentences = []
        for para in paragraphs:
            sents = re.split(r"(?<=[.!?])\s+", para)
            all_sentences.extend([s for s in sents if s.strip()])

        if len(all_sentences) < 4:
            return text

        # Redistribute with varying lengths
        result_paras = []
        i = 0
        while i < len(all_sentences):
            # Randomly choose paragraph length (1-4 sentences)
            para_len = random.choice([1, 2, 3, 3, 4])
            para_sents = all_sentences[i : i + para_len]
            result_paras.append(" ".join(para_sents))
            i += para_len

        return "\n\n".join(result_paras)
