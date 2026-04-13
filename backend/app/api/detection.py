from fastapi import APIRouter, Depends

from ..deps import get_detector, get_sentence_detector
from ..detector.ensemble import EnsembleDetector
from ..detector.sentence_detector import SentenceDetector
from ..schemas.detection import DetectRequest

router = APIRouter(prefix="/api", tags=["detection"])


@router.post("/detect")
async def detect_text(
    req: DetectRequest,
    detector: EnsembleDetector = Depends(get_detector),
):
    return detector.detect(req.text)


@router.post("/detect/sentences")
async def detect_sentences(
    req: DetectRequest,
    sentence_detector: SentenceDetector = Depends(get_sentence_detector),
):
    """Per-sentence detection — returns a heatmap of AI scores."""
    return sentence_detector.detect_sentences(req.text)
