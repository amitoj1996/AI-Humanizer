import numpy as np
from sentence_transformers import SentenceTransformer


class SimilarityChecker:
    """Verify meaning preservation after humanization using
    sentence-transformer embeddings (all-MiniLM-L6-v2, ~90 MB)."""

    def __init__(self):
        print("  Loading sentence-transformer for similarity checking...")
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def score(self, original: str, humanized: str) -> float:
        embeddings = self.model.encode([original, humanized])
        similarity = float(
            np.dot(embeddings[0], embeddings[1])
            / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]) + 1e-8)
        )
        return round(similarity, 4)

    def score_sentences(
        self, originals: list[str], humanized: list[str]
    ) -> list[float]:
        """Score each sentence pair for meaning preservation."""
        if not originals or not humanized:
            return []
        all_texts = originals + humanized
        embs = self.model.encode(all_texts)
        n = len(originals)
        scores = []
        for i in range(min(n, len(humanized))):
            sim = float(
                np.dot(embs[i], embs[n + i])
                / (np.linalg.norm(embs[i]) * np.linalg.norm(embs[n + i]) + 1e-8)
            )
            scores.append(round(sim, 4))
        return scores
