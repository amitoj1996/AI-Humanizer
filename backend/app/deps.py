"""FastAPI dependency functions.

Centralising service lookups here means tests can override them via two
mechanisms:
  - `set_test_registry(fake)` — installs a fake registry used by BOTH the
    FastAPI lifespan and request handlers, so the tests never trigger model
    loading.  This is the important one — lifespan runs before dependency
    overrides take effect, so only pre-installation of a fake works.
  - `app.dependency_overrides[...]` — still works for per-test fine-grained
    overrides of individual services.

`ServiceRegistry.initialise()` is idempotent: calling it on an already-
populated registry (e.g. our FakeRegistry) is a no-op, so the lifespan
harmlessly "re-initialises" a fake without loading anything.
"""
from functools import lru_cache
from typing import Optional

from .detector.ensemble import EnsembleDetector
from .detector.sentence_detector import SentenceDetector
from .humanizer.pipeline import HumanizationPipeline
from .humanizer.similarity import SimilarityChecker


class ServiceRegistry:
    """Holds singleton instances of expensive services.

    Populated on app startup in `main.lifespan`.
    """

    def __init__(self) -> None:
        self.detector: EnsembleDetector | None = None
        self.sentence_detector: SentenceDetector | None = None
        self.similarity: SimilarityChecker | None = None
        self.pipeline: HumanizationPipeline | None = None

    def initialise(self) -> None:
        """Load models once.  Subsequent calls are no-ops."""
        if self.detector is not None:
            return
        print("  Loading detection + similarity models...")
        self.detector = EnsembleDetector()
        self.sentence_detector = SentenceDetector(self.detector)
        self.similarity = SimilarityChecker()
        self.pipeline = HumanizationPipeline(
            self.detector, similarity_checker=self.similarity
        )

    def set_pipeline_model(self, model: str) -> None:
        assert self.detector is not None
        self.pipeline = HumanizationPipeline(
            self.detector, similarity_checker=self.similarity, model=model
        )


# ---------------------------------------------------------------------------
# Registry lookup — tests can install a fake before TestClient starts.
# ---------------------------------------------------------------------------
_test_registry: Optional[ServiceRegistry] = None


@lru_cache(maxsize=1)
def _singleton_registry() -> ServiceRegistry:
    return ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """FastAPI dependency — returns the active service registry.

    Tests call `set_test_registry(FakeRegistry())` to install a fake before
    the FastAPI lifespan fires; both the lifespan and request handlers then
    see the fake.  This is the only way to avoid real model loading in tests,
    because `app.dependency_overrides` takes effect for request handlers only,
    not for the lifespan.
    """
    if _test_registry is not None:
        return _test_registry
    return _singleton_registry()


def set_test_registry(registry: Optional[ServiceRegistry]) -> None:
    """Install a fake registry (or clear it by passing None) for tests."""
    global _test_registry
    _test_registry = registry


def get_detector() -> EnsembleDetector:
    reg = get_registry()
    assert reg.detector is not None, "Detector not initialised"
    return reg.detector


def get_sentence_detector() -> SentenceDetector:
    reg = get_registry()
    assert reg.sentence_detector is not None, "SentenceDetector not initialised"
    return reg.sentence_detector


def get_pipeline() -> HumanizationPipeline:
    reg = get_registry()
    assert reg.pipeline is not None, "Pipeline not initialised"
    return reg.pipeline
