"""FastAPI app setup.

Responsibilities:
  - lifespan (model loading)
  - CORS
  - router registration
  - static frontend (Next.js export) serving

All endpoint logic lives in `app/api/*.py` and injects services via
`app/deps.py`.  Do not add endpoints here.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import detection, health, humanization, models
from .deps import get_registry

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading AI detection models (first run downloads ~1.5 GB)...")
    registry = get_registry()
    registry.initialise()
    print("Ready!")
    yield
    print("Shutting down.")


app = FastAPI(title="AI Humanizer & Detector", version="2.0.0", lifespan=lifespan)

# CORS — allow dev frontend on :3000 to hit the API on :8000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ----
app.include_router(detection.router)
app.include_router(humanization.router)
app.include_router(models.router)
app.include_router(health.router)


# ---------------------------------------------------------------------------
# Serve the static frontend (built Next.js export)
# ---------------------------------------------------------------------------
if STATIC_DIR.exists():
    app.mount("/_next", StaticFiles(directory=STATIC_DIR / "_next"), name="next_assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        file = STATIC_DIR / path
        if file.is_file():
            return FileResponse(file)
        # SPA fallback
        return FileResponse(STATIC_DIR / "index.html")
