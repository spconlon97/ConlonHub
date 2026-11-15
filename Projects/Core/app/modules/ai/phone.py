import hashlib
import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.approvals import router as approvals
from app.core.auth.bootstrap import default_database_path
from app.core.auth.phone_devices import PairingFailed, SqlitePhoneDeviceRepository
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
_logger = logging.getLogger(__name__)

DEVICE_COOKIE = "marvis_device"
# Browsers cap cookie lifetime at 400 days; re-pair after that.
_DEVICE_COOKIE_MAX_AGE = 400 * 24 * 60 * 60


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


def get_phone_device_repository() -> SqlitePhoneDeviceRepository:
    return SqlitePhoneDeviceRepository(default_database_path())


def _audit(audit, principal: Principal, event_type: str, outcome: str, request: Request):
    if audit is None:
        return
    try:
        audit.record_event(
            principal_id=principal.principal_id,
            key_id=None,
            event_type=event_type,
            outcome=outcome,
            method=request.method,
            path=request.url.path,
        )
    except (ValueError, sqlite3.Error):
        _logger.warning("Security audit event could not be persisted.")


def require_paired_phone(
    request: Request,
    principal: Principal = Depends(require_tailscale_principal),
    devices: SqlitePhoneDeviceRepository = Depends(get_phone_device_repository),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
) -> Principal:
    # The Tailscale header alone can be forged by any local program calling
    # 127.0.0.1 directly; the device cookie is only held by a paired browser.
    if devices.verify(request.cookies.get(DEVICE_COOKIE), principal.principal_id) is None:
        _audit(audit, principal, "phone.authenticate", "rejected", request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phone pairing required.",
        )
    return principal


class PairRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    device_name: str | None = Field(default=None, max_length=200)


@router.get("", response_class=HTMLResponse)
def get_phone_page(
    _principal: Principal = Depends(require_tailscale_principal),
):
    return HTMLResponse(_PHONE_PAGE.read_text(encoding="utf-8"))


@router.post("/api/pair")
def pair_phone(
    body: PairRequest,
    http_request: Request,
    principal: Principal = Depends(require_tailscale_principal),
    devices: SqlitePhoneDeviceRepository = Depends(get_phone_device_repository),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
):
    try:
        device, token = devices.redeem(body.code.strip(), principal.principal_id, body.device_name)
    except PairingFailed as error:
        _audit(audit, principal, "phone.pair", "rejected", http_request)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pairing code is invalid or expired.",
        ) from error

    _audit(audit, principal, "phone.pair", "success", http_request)
    response = JSONResponse({"paired": True, "device_name": device.name})
    response.set_cookie(
        DEVICE_COOKIE,
        token,
        max_age=_DEVICE_COOKIE_MAX_AGE,
        path="/phone",
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return response

@router.get("/api/status")
def get_phone_status(
    principal: Principal = Depends(require_paired_phone),
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
    principal: Principal = Depends(require_paired_phone),
    repository: SqliteAIConversationRepository = Depends(
        get_ai_conversation_repository
    ),
    approval_repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return create_ai_response(request, principal, repository, approval_repository)


@router.get("/api/approvals", response_model=approvals.ApprovalList)
def list_phone_approvals(
    principal: Principal = Depends(require_paired_phone),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return approvals.list_pending_approvals(principal, repository)


@router.get("/api/approvals/{request_id}", response_model=approvals.ApprovalView)
def read_phone_approval(
    request_id: str,
    principal: Principal = Depends(require_paired_phone),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return approvals.get_approval(request_id, principal, repository)


@router.post("/api/approvals/{request_id}/approve", response_model=approvals.ApprovalView)
def approve_phone_approval(
    request_id: str,
    http_request: Request,
    principal: Principal = Depends(require_paired_phone),
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
    principal: Principal = Depends(require_paired_phone),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
):
    return approvals.reject_approval(request_id, principal, repository, audit, http_request)
