"""Pytest fixtures — mock out the heavy models so tests run fast AND offline.

Critical design point: FastAPI's lifespan runs when `TestClient(app)` is first
used, BEFORE `app.dependency_overrides` takes effect.  If we rely only on
overrides, the lifespan's `get_registry().initialise()` loads the real 2 GB
of models (and fails on a fresh / offline machine).

Fix: install a FakeRegistry via `set_test_registry()` at module-import time.
The FakeRegistry is already "initialised" (its __init__ creates the stubs),
so `initialise()` is a no-op.  Both the lifespan and the request handlers
see the fake.  No model loading, no network.
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
            "preserved_spans": 0,
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
            "preserved_spans": 0,
        }


class FakeRegistry:
    """A ServiceRegistry shape with no real models.  Already-initialised by
    construction so `initialise()` becomes a no-op when the lifespan fires."""

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
# Module-level: install fake registry BEFORE any test imports `app.main`,
# so the lifespan triggered by TestClient sees the fake and does no work.
# ---------------------------------------------------------------------------
_GLOBAL_FAKE_REGISTRY = FakeRegistry()

# Monkey-patch the Ollama rewriter at module import time too — humanize
# endpoint calls it outside of request-handler dependency injection, so
# dependency_overrides can't help us there.
def _install_module_patches() -> None:
    from app import deps
    from app.humanizer import rewriter as rewriter_mod

    deps.set_test_registry(_GLOBAL_FAKE_REGISTRY)

    async def fake_check_available(self):
        return True

    async def fake_list_models(self):
        return ["fake-model:latest"]

    async def fake_rewrite(self, text, **kwargs):
        return text

    rewriter_mod.OllamaRewriter.check_available = fake_check_available
    rewriter_mod.OllamaRewriter.list_models = fake_list_models
    rewriter_mod.OllamaRewriter.rewrite = fake_rewrite


_install_module_patches()


# ---------------------------------------------------------------------------
# Per-test DB isolation
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("AI_HUMANIZER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_HUMANIZER_DB_PATH", str(db_file))

    from app.db import connection

    connection.reset_engine()
    connection.init_db()
    yield
    connection.reset_engine()


# ---------------------------------------------------------------------------
# TestClient — the FakeRegistry is already installed, no model loading
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_registry() -> FakeRegistry:
    return _GLOBAL_FAKE_REGISTRY


@pytest.fixture
def client(fake_registry):
    from app import deps
    from app.main import app

    # Per-request dependency overrides (still useful — they let individual
    # tests swap in narrower fakes if they want).
    app.dependency_overrides[deps.get_registry] = lambda: fake_registry
    app.dependency_overrides[deps.get_detector] = lambda: fake_registry.detector
    app.dependency_overrides[deps.get_sentence_detector] = lambda: fake_registry.sentence_detector
    app.dependency_overrides[deps.get_pipeline] = lambda: fake_registry.pipeline

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
