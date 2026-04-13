import re

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
    ):
        self.rewriter = OllamaRewriter(model=model)
        self.postprocessor = TextPostProcessor()
        self.structural = StructuralRewriter()
        self.detector = detector
        self.similarity = similarity_checker

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
    ) -> dict:
        intensity_map = {"light": 0.3, "medium": 0.5, "aggressive": 0.8}
        intensity = intensity_map.get(strength, 0.5)

        initial_detection = self.detector.detect(text)

        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        humanized_sentences = []
        sentence_details = []
        total_preserved = 0

        for sent in sentences:
            word_count = len(sent.split())

            # Skip very short sentences — not enough signal to detect
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

            # Protect spans per-sentence so placeholders map back inside
            # the same sentence after rewriting.
            if preserve_citations:
                protected_sent, sent_preserved = preserve.protect(sent)
                total_preserved += len(sent_preserved)
            else:
                protected_sent, sent_preserved = sent, []

            original_score = self.detector.detect(sent)["ai_score"]

            # Generate multiple candidates, pick the best (score after restore).
            best_text = sent
            best_score = original_score
            tested = 0

            for _ in range(candidates_per_sentence):
                try:
                    rewritten = await self.rewriter.rewrite(
                        protected_sent, strength=strength, tone=tone
                    )
                    processed = self.postprocessor.process(rewritten, intensity=intensity)
                    if len(processed.split()) > 12:
                        processed = self.structural.rewrite(processed, intensity=intensity * 0.5)

                    restored = preserve.restore(processed, sent_preserved)
                    score = self.detector.detect(restored)["ai_score"]
                    tested += 1

                    if score < best_score:
                        best_score = score
                        best_text = restored
                except Exception:
                    continue

            humanized_sentences.append(best_text)
            sentence_details.append(
                {
                    "original": sent,
                    "humanized": best_text,
                    "original_ai_score": round(original_score, 4),
                    "best_ai_score": round(best_score, 4),
                    "candidates_tested": tested,
                    "skipped": False,
                }
            )

        humanized_text = " ".join(humanized_sentences)
        final_detection = self.detector.detect(humanized_text)

        result = {
            "original": text,
            "humanized": humanized_text,
            "detection_before": initial_detection,
            "detection_after": final_detection,
            "sentence_details": sentence_details,
            "total_sentences": len(sentences),
            "mode": "sentence-level",
            "preserved_spans": total_preserved,
        }

        if self.similarity:
            result["similarity_score"] = self.similarity.score(text, humanized_text)
            originals = [d["original"] for d in sentence_details if not d["skipped"]]
            humanized = [d["humanized"] for d in sentence_details if not d["skipped"]]
            result["sentence_similarities"] = self.similarity.score_sentences(
                originals, humanized
            )

        return result
