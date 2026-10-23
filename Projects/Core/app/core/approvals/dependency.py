from pathlib import Path

from app.core.approvals.repository import SqliteApprovalRepository


def get_approval_repository() -> SqliteApprovalRepository:
    database_path = (
        Path(__file__).resolve().parents[5] / "Databases" / "core_approvals.db"
    )
    return SqliteApprovalRepository(database_path)
