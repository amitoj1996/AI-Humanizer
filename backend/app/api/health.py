from fastapi import APIRouter, Depends

from ..deps import ServiceRegistry, get_registry

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check(registry: ServiceRegistry = Depends(get_registry)):
    return {"status": "ok", "models_loaded": registry.detector is not None}
