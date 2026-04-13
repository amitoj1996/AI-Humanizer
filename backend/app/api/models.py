from fastapi import APIRouter, Depends

from ..deps import ServiceRegistry, get_registry
from ..humanizer.rewriter import OllamaRewriter
from ..schemas.humanization import ModelSelectRequest

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def list_models():
    ollama = OllamaRewriter()
    available = await ollama.check_available()
    models = await ollama.list_models() if available else []
    return {"ollama_available": available, "models": models}


@router.post("/models/select")
async def select_model(
    req: ModelSelectRequest,
    registry: ServiceRegistry = Depends(get_registry),
):
    registry.set_pipeline_model(req.model)
    return {"selected_model": req.model}


@router.get("/tones")
async def list_tones():
    return {
        "tones": [
            {
                "id": "general",
                "label": "General",
                "description": "Natural, balanced rewriting",
            },
            {
                "id": "academic",
                "label": "Academic",
                "description": "Scholarly but natural — grad-student essay style",
            },
            {
                "id": "casual",
                "label": "Casual",
                "description": "Texting a friend / Reddit comment style",
            },
            {
                "id": "blog",
                "label": "Blog",
                "description": "Engaging, conversational blog post style",
            },
            {
                "id": "professional",
                "label": "Professional",
                "description": "Polished business writing style",
            },
        ]
    }
