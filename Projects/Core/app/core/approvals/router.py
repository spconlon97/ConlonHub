import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from app.core.approvals.dependency import get_approval_repository
from app.core.approvals.models import ApprovalRequest, ApprovalStatus
from app.core.approvals.repository import (
    ApprovalNotFound,
    ApprovalNotPending,
    SqliteApprovalRepository,
)
from app.core.approvals.service import approve_and_execute, reject
from app.core.auth.audit import SqliteAuditRepository
from app.core.auth.dependency import get_audit_repository, require_principal
from app.core.auth.principal import Principal
from app.core.capabilities.registry import CapabilityRegistry


router = APIRouter(prefix="/approvals", tags=["Approvals"])
_logger = logging.getLogger(__name__)


class ApprovalView(BaseModel):
    request_id: str
    capability: str
    arguments: dict
    summary: str
    status: str
    created_at: str
    expires_at: str
    decided_at: str | None
    outcome: str | None


class ApprovalList(BaseModel):
    approvals: list[ApprovalView]


def get_capability_registry() -> CapabilityRegistry:
    # Deferred import keeps approval storage free of application-module imports.
    from app.modules.loader import get_module_instance

    return get_module_instance("AI Assistant").registry


def _view(request: ApprovalRequest) -> ApprovalView:
    return ApprovalView(
        request_id=request.request_id,
        capability=request.capability,
        arguments=request.arguments,
        summary=request.summary,
        status=request.status.value,
        created_at=request.created_at,
        expires_at=request.expires_at,
        decided_at=request.decided_at,
        outcome=request.outcome,
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Approval request was not found.",
    )


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


def list_pending_approvals(principal, repository) -> ApprovalList:
    return ApprovalList(
        approvals=[_view(item) for item in repository.list_pending(principal.principal_id)]
    )


def get_approval(request_id, principal, repository) -> ApprovalView:
    try:
        return _view(repository.get(request_id, principal.principal_id))
    except ApprovalNotFound as error:
        raise _not_found() from error


def approve_approval(request_id, principal, repository, registry, audit, http_request):
    try:
        result = approve_and_execute(
            repository, registry, request_id, principal.principal_id
        )
    except ApprovalNotFound as error:
        _audit(audit, principal, "approval.approve", "rejected", http_request)
        raise _not_found() from error
    except ApprovalNotPending as error:
        _audit(audit, principal, "approval.approve", "rejected", http_request)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    outcome = "success" if result.status == ApprovalStatus.EXECUTED else "error"
    _audit(audit, principal, "approval.approve", outcome, http_request)
    return _view(result)


def reject_approval(request_id, principal, repository, audit, http_request):
    try:
        result = reject(repository, request_id, principal.principal_id)
    except ApprovalNotFound as error:
        _audit(audit, principal, "approval.reject", "rejected", http_request)
        raise _not_found() from error
    except ApprovalNotPending as error:
        _audit(audit, principal, "approval.reject", "rejected", http_request)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    _audit(audit, principal, "approval.reject", "success", http_request)
    return _view(result)


@router.get("", response_model=ApprovalList)
def list_approvals(
    principal: Principal = Depends(require_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return list_pending_approvals(principal, repository)


@router.get("/{request_id}", response_model=ApprovalView)
def read_approval(
    request_id: str,
    principal: Principal = Depends(require_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
):
    return get_approval(request_id, principal, repository)


@router.post("/{request_id}/approve", response_model=ApprovalView)
def approve(
    request_id: str,
    http_request: Request,
    principal: Principal = Depends(require_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
    registry: CapabilityRegistry = Depends(get_capability_registry),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
):
    return approve_approval(request_id, principal, repository, registry, audit, http_request)


@router.post("/{request_id}/reject", response_model=ApprovalView)
def reject_request(
    request_id: str,
    http_request: Request,
    principal: Principal = Depends(require_principal),
    repository: SqliteApprovalRepository = Depends(get_approval_repository),
    audit: SqliteAuditRepository | None = Depends(get_audit_repository),
):
    return reject_approval(request_id, principal, repository, audit, http_request)
