"""Pytest fixtures — mock out the heavy models so tests run fast.

Pattern: override `get_registry` with a FakeRegistry that provides lightweight
stub services.  No PyTorch / HuggingFace / sentence-transformers get loaded.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Stub services (no model loading)
# ---------------------------------------------------------------------------
class FakeDetector:
    def detect(self, text: str) -> dict:
        # Higher AI score if text contains "Moreover" / "Furthermore" — just
        # enough realism for smoke tests.
        ai = 0.8 if any(m in text for m in ("Moreover", "Furthermore")) else 0.2
        return {
            "ai_score": ai,
            "human_score": 1 - ai,
            "verdict": "AI-generated" if ai > 0.6 else "Human-written",
            "breakdown": {
                "classifier": {"ai_probability": ai, "human_probability": 1 - ai},
                "perplexity": {
                    "perplexity": 15.0,
                    "burstiness": 0.3,
                    "combined_ai_signal": ai,
                },
                "linguistic": {
                    "sentence_length_cv": 0.4,
                    "type_token_ratio": 0.6,
                    "ai_marker_density": 2.0 if ai > 0.5 else 0.2,
                    "contraction_rate": 0.1,
                    "ai_signal": ai,
                    "details": {
                        "word_count": len(text.split()),
                        "sentence_count": text.count(".") or 1,
                        "ai_markers_found": 2 if ai > 0.5 else 0,
                    },
                },
            },
        }


class FakeSentenceDetector:
    def __init__(self, detector: FakeDetector):
        self.detector = detector

    def detect_sentences(self, text: str) -> dict:
        overall = self.detector.detect(text)
        sents = [s.strip() for s in text.split(".") if s.strip()]
        sentence_results = [
            {
                "sentence": s,
                "ai_score": self.detector.detect(s + ".")["ai_score"],
                "verdict": "AI-generated",
                "word_count": len(s.split()),
            }
            for s in sents
        ]
        avg = (
            sum(r["ai_score"] for r in sentence_results) / len(sentence_results)
            if sentence_results
            else 0.0
        )
        return {
            "overall": overall,
            "average_sentence_ai": avg,
            "sentences": sentence_results,
            "total_sentences": len(sents),
            "scored_sentences": len(sents),
        }


class FakePipeline:
    async def humanize(self, text: str, **kwargs) -> dict:
        return {
            "original": text,
            "humanized": text.replace("Moreover, ", "").replace("Furthermore, ", ""),
            "detection_before": {"ai_score": 0.8, "verdict": "AI-generated", "breakdown": {}, "human_score": 0.2},
            "detection_after": {"ai_score": 0.2, "verdict": "Human-written", "breakdown": {}, "human_score": 0.8},
            "iterations": [{"iteration": 1, "strength": "medium", "ai_score": 0.2, "verdict": "Human-written"}],
            "total_iterations": 1,
            "mode": "full-text",
            "similarity_score": 0.95,
        }

    async def humanize_sentences(self, text: str, **kwargs) -> dict:
        return {
            "original": text,
            "humanized": text.replace("Moreover, ", "").replace("Furthermore, ", ""),
            "detection_before": {"ai_score": 0.8, "verdict": "AI-generated", "breakdown": {}, "human_score": 0.2},
            "detection_after": {"ai_score": 0.15, "verdict": "Human-written", "breakdown": {}, "human_score": 0.85},
            "sentence_details": [],
            "total_sentences": 1,
            "mode": "sentence-level",
            "similarity_score": 0.92,
        }


class FakeRegistry:
    def __init__(self) -> None:
        self.detector = FakeDetector()
        self.sentence_detector = FakeSentenceDetector(self.detector)
        self.similarity = None
        self.pipeline = FakePipeline()

    def initialise(self) -> None:  # noqa: D401 — matches real registry API
        pass

    def set_pipeline_model(self, model: str) -> None:
        pass


# ---------------------------------------------------------------------------
# FastAPI TestClient with overridden dependencies
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_registry() -> FakeRegistry:
    return FakeRegistry()


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """Each test gets a fresh SQLite file in a tmp dir.  No app data polluted."""
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("AI_HUMANIZER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_HUMANIZER_DB_PATH", str(db_file))

    # Reset cached engine so it picks up the new path
    from app.db import connection

    connection.reset_engine()
    connection.init_db()
    yield
    connection.reset_engine()


@pytest.fixture
def client(fake_registry, monkeypatch):
    """TestClient with mocked services.  Use this in every test."""
    # Monkey-patch OllamaRewriter globally so humanize endpoint doesn't actually
    # try to hit localhost:11434
    from app.humanizer import rewriter as rewriter_mod

    async def fake_check_available(self):
        return True

    async def fake_list_models(self):
        return ["fake-model:latest"]

    async def fake_rewrite(self, text, **kwargs):
        return text

    monkeypatch.setattr(rewriter_mod.OllamaRewriter, "check_available", fake_check_available)
    monkeypatch.setattr(rewriter_mod.OllamaRewriter, "list_models", fake_list_models)
    monkeypatch.setattr(rewriter_mod.OllamaRewriter, "rewrite", fake_rewrite)

    # Import after monkeypatch so any module-level init uses the fakes
    from app import deps
    from app.main import app

    app.dependency_overrides[deps.get_registry] = lambda: fake_registry
    app.dependency_overrides[deps.get_detector] = lambda: fake_registry.detector
    app.dependency_overrides[deps.get_sentence_detector] = lambda: fake_registry.sentence_detector
    app.dependency_overrides[deps.get_pipeline] = lambda: fake_registry.pipeline

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
