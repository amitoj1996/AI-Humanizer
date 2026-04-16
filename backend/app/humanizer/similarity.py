import numpy as np
from sentence_transformers import SentenceTransformer


class SimilarityChecker:
    """Verify meaning preservation after humanization using
    sentence-transformer embeddings (all-MiniLM-L6-v2, ~90 MB).

    Exposes `encode()` / `cosine_against()` so hot loops (best-of-N per
    sentence) can encode the original ONCE and reuse it across candidates
    instead of re-encoding on every `score()` call. The
    sentence-transformers docs explicitly recommend caching frequent
    query embeddings for exactly this pattern.
    """

    def __init__(self):
        print("  Loading sentence-transformer for similarity checking...")
        # normalize_embeddings at encode-time lets us skip the norm-division
        # on every cosine call — cheaper per-comparison in hot loops.
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

    def encode(self, text: str) -> np.ndarray:
        """Return a normalized embedding for a single string.

        Pre-normalizing means cosine similarity is a plain dot product,
        which is measurably faster when running against many candidates.
        """
        emb = self.model.encode(text, normalize_embeddings=True)
        return np.asarray(emb, dtype=np.float32)

    def cosine_against(self, precomputed_original: np.ndarray, candidate: str) -> float:
        """Cosine similarity between a cached original embedding and a
        fresh candidate text. Assumes `precomputed_original` is already
        L2-normalized (as returned by `encode()`)."""
        cand = self.encode(candidate)
        return float(round(float(np.dot(precomputed_original, cand)), 4))

    def cosine_batch_against(
        self, precomputed_original: np.ndarray, candidates: list[str]
    ) -> list[float]:
        """Cosine similarity of a cached original embedding against N
        candidates in one padded forward pass. Used by best-of-N sentence
        mode to avoid N separate encode() calls.
        """
        if not candidates:
            return []
        embs = self.model.encode(candidates, normalize_embeddings=True)
        # embs shape: (N, dim) — dot each row with the cached vector.
        sims = np.asarray(embs, dtype=np.float32) @ precomputed_original
        return [float(round(float(s), 4)) for s in sims]

    def score(self, original: str, humanized: str) -> float:
        # Batched encode + normalize — one GPU call instead of two.
        embeddings = self.model.encode(
            [original, humanized], normalize_embeddings=True
        )
        return float(round(float(np.dot(embeddings[0], embeddings[1])), 4))

    def score_sentences(
        self, originals: list[str], humanized: list[str]
    ) -> list[float]:
        """Score each sentence pair for meaning preservation."""
        if not originals or not humanized:
            return []
        all_texts = originals + humanized
        embs = self.model.encode(all_texts, normalize_embeddings=True)
        n = len(originals)
        scores = []
        for i in range(min(n, len(humanized))):
            sim = float(np.dot(embs[i], embs[n + i]))
            scores.append(round(sim, 4))
        return scores
