from fastapi import APIRouter
from server.app.config import GENERATOR_VERSION

router = APIRouter()


@router.get("/health")
@router.get("/api/health")
def health():
    import importlib.util
    com_available = importlib.util.find_spec("comtypes") is not None
    return {
        "status": "ok",
        "comtypes": com_available,
        "generator": GENERATOR_VERSION,
    }
