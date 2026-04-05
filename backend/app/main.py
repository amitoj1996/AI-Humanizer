from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .detector.ensemble import EnsembleDetector
from .detector.sentence_detector import SentenceDetector
from .humanizer.pipeline import HumanizationPipeline
from .humanizer.rewriter import OllamaRewriter
from .humanizer.similarity import SimilarityChecker

STATIC_DIR = Path(__file__).parent.parent / "static"

# ---------------------------------------------------------------------------
# Globals (populated during lifespan startup)
# ---------------------------------------------------------------------------
detector: EnsembleDetector | None = None
sentence_detector: SentenceDetector | None = None
similarity: SimilarityChecker | None = None
pipeline: HumanizationPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global detector, sentence_detector, similarity, pipeline
    print("Loading AI detection models (first run downloads ~1.5 GB)...")
    detector = EnsembleDetector()
    sentence_detector = SentenceDetector(detector)
    similarity = SimilarityChecker()
    pipeline = HumanizationPipeline(detector, similarity_checker=similarity)
    print("Ready!")
    yield
    print("Shutting down.")


app = FastAPI(title="AI Humanizer & Detector", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class DetectRequest(BaseModel):
    text: str = Field(..., min_length=50)


class HumanizeRequest(BaseModel):
    text: str = Field(..., min_length=50)
    strength: str = Field("medium", pattern="^(light|medium|aggressive)$")
    tone: str = Field("general", pattern="^(general|academic|casual|blog|professional)$")
    max_iterations: int = Field(3, ge=1, le=5)
    target_score: float = Field(0.35, ge=0.0, le=1.0)
    mode: str = Field("sentence", pattern="^(full|sentence)$")
    candidates_per_sentence: int = Field(3, ge=1, le=5)


class ModelSelectRequest(BaseModel):
    model: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/detect")
async def detect_text(req: DetectRequest):
    return detector.detect(req.text)


@app.post("/api/detect/sentences")
async def detect_sentences(req: DetectRequest):
    """Per-sentence detection — returns a heatmap of AI scores."""
    return sentence_detector.detect_sentences(req.text)


@app.post("/api/humanize")
async def humanize_text(req: HumanizeRequest):
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
    else:
        return await pipeline.humanize(
            req.text,
            strength=req.strength,
            tone=req.tone,
            max_iterations=req.max_iterations,
            target_score=req.target_score,
        )


@app.get("/api/models")
async def list_models():
    ollama = OllamaRewriter()
    available = await ollama.check_available()
    models = await ollama.list_models() if available else []
    return {"ollama_available": available, "models": models}


@app.post("/api/models/select")
async def select_model(req: ModelSelectRequest):
    global pipeline
    pipeline = HumanizationPipeline(detector, similarity_checker=similarity, model=req.model)
    return {"selected_model": req.model}


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "models_loaded": detector is not None}


@app.get("/api/tones")
async def list_tones():
    return {
        "tones": [
            {"id": "general", "label": "General", "description": "Natural, balanced rewriting"},
            {"id": "academic", "label": "Academic", "description": "Scholarly but natural — grad-student essay style"},
            {"id": "casual", "label": "Casual", "description": "Texting a friend / Reddit comment style"},
            {"id": "blog", "label": "Blog", "description": "Engaging, conversational blog post style"},
            {"id": "professional", "label": "Professional", "description": "Polished business writing style"},
        ]
    }


# ---------------------------------------------------------------------------
# Serve the static frontend (built Next.js export)
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    # Serve Next.js _next assets
    app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next_assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file = STATIC_DIR / path
        if file.is_file():
            return FileResponse(file)
        # SPA fallback
        return FileResponse(STATIC_DIR / "index.html")
