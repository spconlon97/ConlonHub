from fastapi import APIRouter

from app.modules.loader import get_module_instance

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.get("/status")
def get_ai_status():
    assistant = get_module_instance("AI Assistant")

    return {
        "name": assistant.name,
        "version": assistant.version,
        "status": assistant.status(),
    }
