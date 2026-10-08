from fastapi import APIRouter, Request

from server.config import settings


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request):
    predictor = getattr(request.app.state, "predictor", None)

    return {
        "status": "online" if predictor is not None else "starting",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "device": str(predictor.device) if predictor is not None else None,
        "classes": predictor.actions if predictor is not None else [],
        "sequence_length": settings.sequence_length,
        "input_size": settings.input_size,
    }
