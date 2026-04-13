from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_pipeline
from ..humanizer.pipeline import HumanizationPipeline
from ..humanizer.rewriter import OllamaRewriter
from ..schemas.humanization import HumanizeRequest

router = APIRouter(prefix="/api", tags=["humanization"])


@router.post("/humanize")
async def humanize_text(
    req: HumanizeRequest,
    pipeline: HumanizationPipeline = Depends(get_pipeline),
):
    ollama = OllamaRewriter()
    if not await ollama.check_available():
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start it with: ollama serve",
        )

    if req.mode == "sentence":
        return await pipeline.humanize_sentences(
            req.text,
            strength=req.strength,
            tone=req.tone,
            candidates_per_sentence=req.candidates_per_sentence,
            target_score=req.target_score,
        )
    return await pipeline.humanize(
        req.text,
        strength=req.strength,
        tone=req.tone,
        max_iterations=req.max_iterations,
        target_score=req.target_score,
    )
