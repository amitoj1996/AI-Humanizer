"""FastAPI dependency functions.

Centralising service lookups here means tests can override them via
`app.dependency_overrides` without loading the real 2 GB of models.
"""
from functools import lru_cache

from .detector.ensemble import EnsembleDetector
from .detector.sentence_detector import SentenceDetector
from .humanizer.pipeline import HumanizationPipeline
from .humanizer.similarity import SimilarityChecker


class ServiceRegistry:
    """Holds singleton instances of expensive services.

    Populated on app startup in `main.lifespan`.  Tests replace this via
    `app.dependency_overrides[get_registry] = lambda: FakeRegistry()`.
    """

    def __init__(self) -> None:
        self.detector: EnsembleDetector | None = None
        self.sentence_detector: SentenceDetector | None = None
        self.similarity: SimilarityChecker | None = None
        self.pipeline: HumanizationPipeline | None = None

    def initialise(self) -> None:
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


@lru_cache(maxsize=1)
def _singleton_registry() -> ServiceRegistry:
    return ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """FastAPI dependency — returns the process-wide service registry."""
    return _singleton_registry()


def get_detector() -> EnsembleDetector:
    reg = _singleton_registry()
    assert reg.detector is not None, "Detector not initialised"
    return reg.detector


def get_sentence_detector() -> SentenceDetector:
    reg = _singleton_registry()
    assert reg.sentence_detector is not None, "SentenceDetector not initialised"
    return reg.sentence_detector


def get_pipeline() -> HumanizationPipeline:
    reg = _singleton_registry()
    assert reg.pipeline is not None, "Pipeline not initialised"
    return reg.pipeline
