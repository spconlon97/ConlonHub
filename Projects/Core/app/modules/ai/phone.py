import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.core.auth.principal import Principal
from app.modules.loader import get_module_instance
from app.modules.ai.repository import SqliteAIConversationRepository
from app.modules.ai.router import (
    AIResponse,
    AIResponseRequest,
    create_ai_response,
    get_ai_conversation_repository,
)


router = APIRouter(prefix="/phone", tags=["MARVIS Phone"])
_PHONE_PAGE = Path(__file__).with_name("phone.html")


def require_tailscale_principal(request: Request) -> Principal:
    login = request.headers.get("Tailscale-User-Login", "").strip()
    if not login:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Open this page through its private Tailscale Serve address.",
        )

    identity_digest = hashlib.sha256(login.casefold().encode("utf-8")).hexdigest()
    display_name = request.headers.get("Tailscale-User-Name", "").strip() or login
    return Principal(
        principal_id=f"tailscale:{identity_digest}",
        name=display_name,
    )


@router.get("", response_class=HTMLResponse)
def get_phone_page(
    _principal: Principal = Depends(require_tailscale_principal),
):
    return HTMLResponse(_PHONE_PAGE.read_text(encoding="utf-8"))

@router.get("/api/status")
def get_phone_status(
    principal: Principal = Depends(require_tailscale_principal),
):
    assistant = get_module_instance("AI Assistant")
    details = assistant.status_details()
    return {
        "status": details["status"],
        "model": details["model"],
        "user": principal.name,
    }


@router.post("/api/respond", response_model=AIResponse)
def create_phone_response(
    request: AIResponseRequest,
    principal: Principal = Depends(require_tailscale_principal),
    repository: SqliteAIConversationRepository = Depends(
        get_ai_conversation_repository
    ),
):
    return create_ai_response(request, principal, repository)
