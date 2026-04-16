import asyncio
import re

from ..config import (
    MAX_CONCURRENT_REWRITES,
    MIN_SEMANTIC_SIMILARITY,
    OLLAMA_CANDIDATE_MODELS,
)
from ..detector.ensemble import EnsembleDetector
from . import preserve
from .postprocess import TextPostProcessor
from .rewriter import OllamaRewriter
from .similarity import SimilarityChecker
from .structural import StructuralRewriter


class HumanizationPipeline:
    """Advanced humanization pipeline with two modes:

    1. **Full-text mode** (original) — rewrites entire text, checks score, iterates.
    2. **Sentence-level mode** (NeurIPS technique) — splits into sentences,
       generates multiple candidates per sentence, picks the one with the
       lowest AI score.  Much more effective against modern detectors.
    """

    STRENGTH_LADDER = ["light", "medium", "aggressive"]

    def __init__(
        self,
        detector: EnsembleDetector,
        similarity_checker: SimilarityChecker | None = None,
        model: str | None = None,
        candidate_models: list[str] | None = None,
    ):
        self.rewriter = OllamaRewriter(model=model)
        self.postprocessor = TextPostProcessor()
        self.structural = StructuralRewriter()
        self.detector = detector
        self.similarity = similarity_checker
        # Sentence-mode candidates are drawn by rotating through this list.
        # If the caller passes an explicit primary `model`, pin it to the
        # front so the first candidate comes from the user-selected model;
        # we still diversify the remaining candidates.
        cands = list(candidate_models) if candidate_models else list(OLLAMA_CANDIDATE_MODELS)
        if model and model in cands:
            cands.remove(model)
        if model:
            cands.insert(0, model)
        self.candidate_models = cands or [self.rewriter.model]

    # ------------------------------------------------------------------
    # Full-text humanization (original approach)
    # ------------------------------------------------------------------
    async def humanize(
        self,
        text: str,
        strength: str = "medium",
        tone: str = "general",
        max_iterations: int = 3,
        target_score: float = 0.35,
        preserve_citations: bool = True,
    ) -> dict:
        intensity_map = {"light": 0.3, "medium": 0.5, "aggressive": 0.8}
        intensity = intensity_map.get(strength, 0.5)

        initial_detection = self.detector.detect(text)

        # Protect citations / quotes / code / LaTeX.  We work on the
        # placeholdered version for the whole loop; restore at the end.
        if preserve_citations:
            working_text, preserved = preserve.protect(text)
        else:
            working_text, preserved = text, []

        current_text = working_text
        current_strength = strength
        iterations = []

        for i in range(max_iterations):
            rewritten = await self.rewriter.rewrite(
                current_text, strength=current_strength, tone=tone
            )
            processed = self.postprocessor.process(rewritten, intensity=intensity)
            processed = self.structural.rewrite(processed, intensity=intensity)
            # Score the restored (placeholder-free) version so the detection
            # signal reflects what the user actually sees.
            scoreable = preserve.restore(processed, preserved)
            detection = self.detector.detect(scoreable)

            iterations.append(
                {
                    "iteration": i + 1,
                    "strength": current_strength,
                    "ai_score": detection["ai_score"],
                    "verdict": detection["verdict"],
                }
            )
            current_text = processed

            if detection["ai_score"] <= target_score:
                break

            idx = (
                self.STRENGTH_LADDER.index(current_strength)
                if current_strength in self.STRENGTH_LADDER
                else 1
            )
            current_strength = self.STRENGTH_LADDER[
                min(idx + 1, len(self.STRENGTH_LADDER) - 1)
            ]
            intensity = min(1.0, intensity + 0.15)

        final_text = preserve.restore(current_text, preserved)
        final_detection = self.detector.detect(final_text)

        result = {
            "original": text,
            "humanized": final_text,
            "detection_before": initial_detection,
            "detection_after": final_detection,
            "iterations": iterations,
            "total_iterations": len(iterations),
            "mode": "full-text",
            "preserved_spans": len(preserved),
        }

        if self.similarity:
            result["similarity_score"] = self.similarity.score(text, final_text)

        return result

    # ------------------------------------------------------------------
    # Sentence-level humanization (NeurIPS adversarial technique)
    # ------------------------------------------------------------------
    async def humanize_sentences(
        self,
        text: str,
        strength: str = "medium",
        tone: str = "general",
        candidates_per_sentence: int = 3,
        target_score: float = 0.35,
        preserve_citations: bool = True,
        max_passes: int = 2,
    ) -> dict:
        """Sentence-level humanization with temperature-escalated best-of-N
        per sentence, then recursive passes until the whole-document score
        hits target or max_passes is exhausted.

        Recursive paraphrasing is the technique from Krishna et al.
        (arXiv:2303.13408) and Adversarial Paraphrasing (arXiv:2506.07001)
        — one pass often under-moves the score, but 2-3 passes reliably
        clear modern classifiers.
        """
        intensity_map = {"light": 0.3, "medium": 0.5, "aggressive": 0.8}
        intensity = intensity_map.get(strength, 0.5)

        initial_detection = self.detector.detect(text)

        current_text = text
        passes = []

        for pass_idx in range(max_passes):
            pass_result = await self._single_sentence_pass(
                current_text,
                strength=strength,
                tone=tone,
                intensity=intensity,
                candidates_per_sentence=candidates_per_sentence,
                preserve_citations=preserve_citations,
            )
            passes.append(
                {
                    "pass": pass_idx + 1,
                    "ai_score": pass_result["final_detection"]["ai_score"],
                    "verdict": pass_result["final_detection"]["verdict"],
                    "sentences": pass_result["total_sentences"],
                }
            )
            current_text = pass_result["humanized_text"]

            if pass_result["final_detection"]["ai_score"] <= target_score:
                break

        final_detection = self.detector.detect(current_text)

        result = {
            "original": text,
            "humanized": current_text,
            "detection_before": initial_detection,
            "detection_after": final_detection,
            "sentence_details": pass_result["sentence_details"],
            "total_sentences": pass_result["total_sentences"],
            "mode": "sentence-level",
            "preserved_spans": pass_result["total_preserved"],
            "passes": passes,
            "total_passes": len(passes),
        }

        if self.similarity:
            result["similarity_score"] = self.similarity.score(text, current_text)
            originals = [
                d["original"] for d in pass_result["sentence_details"] if not d["skipped"]
            ]
            humanized = [
                d["humanized"] for d in pass_result["sentence_details"] if not d["skipped"]
            ]
            result["sentence_similarities"] = self.similarity.score_sentences(
                originals, humanized
            )

        return result

    async def _single_sentence_pass(
        self,
        text: str,
        strength: str,
        tone: str,
        intensity: float,
        candidates_per_sentence: int,
        preserve_citations: bool,
    ) -> dict:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        humanized_sentences = []
        sentence_details = []
        total_preserved = 0

        # Temperature ladder for candidate diversity — higher temp = more
        # variance, more chance of escaping the LLM's default register.
        temps = [0.85, 1.0, 1.15, 1.3]

        for sent in sentences:
            word_count = len(sent.split())

            if word_count < 6:
                humanized_sentences.append(sent)
                sentence_details.append(
                    {
                        "original": sent,
                        "humanized": sent,
                        "original_ai_score": None,
                        "best_ai_score": None,
                        "candidates_tested": 0,
                        "skipped": True,
                    }
                )
                continue

            if preserve_citations:
                protected_sent, sent_preserved = preserve.protect(sent)
                total_preserved += len(sent_preserved)
            else:
                protected_sent, sent_preserved = sent, []

            # Fast path: rank candidates with classifier-only (quick_score),
            # then run the full ensemble once on the winner. The full
            # detector is 30-60x slower than the classifier because of
            # the Qwen-4B perplexity forward pass per sentence.
            original_score = self.detector.quick_score(sent)

            # Cache the original's normalized embedding — we reuse it
            # against every candidate. Without this, similarity.score()
            # re-encodes `sent` on every iteration.
            original_emb = (
                self.similarity.encode(sent) if self.similarity is not None else None
            )

            # --- Generate N candidates concurrently --------------------
            # Each candidate hits a different model on Ollama (round-robin
            # through self.candidate_models), so with OLLAMA_NUM_PARALLEL>=2
            # or distinct candidate models they run truly in parallel on
            # separate GPUs. A semaphore caps fan-out so we don't flood
            # Ollama's queue.
            sem = asyncio.Semaphore(max(1, MAX_CONCURRENT_REWRITES))

            async def _generate(i: int) -> str | None:
                async with sem:
                    candidate_model = self.candidate_models[
                        i % len(self.candidate_models)
                    ]
                    try:
                        # Sentence rewrites have tight input+output token
                        # budgets compared to full-document mode. Smaller
                        # num_ctx frees VRAM and lets Ollama run more
                        # concurrent requests safely; smaller num_predict
                        # caps generation at roughly 4x the input length,
                        # which is plenty for a paraphrase and avoids the
                        # default 4096-token overshoot that dominates
                        # eval_duration on short inputs.
                        sent_tok_est = max(32, len(protected_sent) // 3)
                        rewritten = await self.rewriter.rewrite(
                            protected_sent,
                            strength=strength,
                            tone=tone,
                            temperature=temps[min(i, len(temps) - 1)],
                            model=candidate_model,
                            num_ctx=1024,
                            num_predict=min(512, sent_tok_est * 4),
                        )
                    except Exception:
                        return None
                    processed = self.postprocessor.process(
                        rewritten, intensity=intensity
                    )
                    if len(processed.split()) > 12:
                        processed = self.structural.rewrite(
                            processed, intensity=intensity * 0.5
                        )
                    return preserve.restore(processed, sent_preserved)

            raw_candidates = await asyncio.gather(
                *(_generate(i) for i in range(candidates_per_sentence))
            )
            candidates = [c for c in raw_candidates if c]

            # --- Similarity gate (batched) ------------------------------
            rejected_low_similarity = 0
            survivors: list[tuple[str, float | None]] = []
            if self.similarity is not None and original_emb is not None and candidates:
                sims = self.similarity.cosine_batch_against(original_emb, candidates)
                for cand, sim in zip(candidates, sims):
                    if sim < MIN_SEMANTIC_SIMILARITY:
                        rejected_low_similarity += 1
                        continue
                    survivors.append((cand, sim))
            else:
                survivors = [(c, None) for c in candidates]

            # --- Classifier scoring (batched) --------------------------
            best_text = sent
            best_score = original_score
            best_similarity: float | None = None
            if survivors:
                survivor_texts = [c for c, _ in survivors]
                scores = self.detector.quick_score_batch(survivor_texts)
                # Pick lowest AI score that also beats the original.
                for (cand, sim), score in zip(survivors, scores):
                    if score < best_score:
                        best_score = score
                        best_text = cand
                        best_similarity = sim

            humanized_sentences.append(best_text)
            sentence_details.append(
                {
                    "original": sent,
                    "humanized": best_text,
                    "original_ai_score": round(original_score, 4),
                    "best_ai_score": round(best_score, 4),
                    "best_similarity": (
                        round(best_similarity, 4) if best_similarity is not None else None
                    ),
                    "candidates_tested": len(candidates),
                    "rejected_low_similarity": rejected_low_similarity,
                    "skipped": False,
                }
            )

        humanized_text = " ".join(humanized_sentences)
        return {
            "humanized_text": humanized_text,
            "final_detection": self.detector.detect(humanized_text),
            "sentence_details": sentence_details,
            "total_sentences": len(sentences),
            "total_preserved": total_preserved,
        }
