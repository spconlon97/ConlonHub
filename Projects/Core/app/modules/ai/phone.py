import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.core.approvals import router as approvals
from app.core.approvals.dependency import get_approval_repository
from app.core.approvals.repository import SqliteApprovalRepository
from app.core.auth.audit import SqliteAuditRepository
from app.core.auth.dependency import get_audit_repository
from app.core.auth.principal import Principal
from app.core.capabilities.registry import CapabilityRegistry
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
    approval_repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return create_ai_response(request, principal, repository, approval_repository)


@router.get("/api/approvals", response_model=approvals.ApprovalList)
def list_phone_approvals(
    principal: Principal = Depends(require_tailscale_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return approvals.list_pending_approvals(principal, repository)


@router.get("/api/approvals/{request_id}", response_model=approvals.ApprovalView)
def read_phone_approval(
    request_id: str,
    principal: Principal = Depends(require_tailscale_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return approvals.get_approval(request_id, principal, repository)


@router.post("/api/approvals/{request_id}/approve", response_model=approvals.ApprovalView)
def approve_phone_approval(
    request_id: str,
    http_request: Request,
    principal: Principal = Depends(require_tailscale_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
    registry: CapabilityRegistry = Depends(approvals.get_capability_registry),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
):
    return approvals.approve_approval(
        request_id, principal, repository, registry, audit, http_request
    )


@router.post("/api/approvals/{request_id}/reject", response_model=approvals.ApprovalView)
def reject_phone_approval(
    request_id: str,
    http_request: Request,
    principal: Principal = Depends(require_tailscale_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
):
    return approvals.reject_approval(request_id, principal, repository, audit, http_request)
