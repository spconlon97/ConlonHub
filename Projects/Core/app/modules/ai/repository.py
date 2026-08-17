import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.database import migrate_database


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationNotFound(ValueError):
    pass


class SqliteAIConversationRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        migrate_database(self.database_path, "ai")

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create_conversation(self, principal_id: str) -> str:
        conversation_id = str(uuid.uuid4())
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO ai_conversations (
                    conversation_id, principal_id, created_at
                ) VALUES (?, ?, ?)
                """,
                (conversation_id, principal_id, _utc_now_iso()),
            )
            connection.commit()
        return conversation_id

    def claim_request_quota(
        self,
        principal_id: str,
        *,
        maximum: int,
        window_seconds: int = 60,
        now: datetime | None = None,
    ) -> bool:
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            raise ValueError("maximum must be a positive integer.")
        if (
            not isinstance(window_seconds, int)
            or isinstance(window_seconds, bool)
            or window_seconds < 1
        ):
            raise ValueError("window_seconds must be a positive integer.")

        timestamp = now or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            raise ValueError("now must be timezone-aware.")
        timestamp = timestamp.astimezone(timezone.utc)
        cutoff = (timestamp - timedelta(seconds=window_seconds)).isoformat()

        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "DELETE FROM ai_request_events WHERE occurred_at < ?",
                    (cutoff,),
                )
                count = connection.execute(
                    """
                    SELECT COUNT(*) FROM ai_request_events
                    WHERE principal_id = ? AND occurred_at >= ?
                    """,
                    (principal_id, cutoff),
                ).fetchone()[0]
                if count >= maximum:
                    connection.rollback()
                    return False
                connection.execute(
                    """
                    INSERT INTO ai_request_events (principal_id, occurred_at)
                    VALUES (?, ?)
                    """,
                    (principal_id, timestamp.isoformat()),
                )
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def list_conversations(
        self, principal_id: str, *, limit: int = 20, offset: int = 0
    ):
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100.")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a non-negative integer.")

        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    conversation.conversation_id,
                    conversation.created_at,
                    COUNT(message.id) AS message_count
                FROM ai_conversations AS conversation
                LEFT JOIN ai_messages AS message
                    ON message.conversation_id = conversation.conversation_id
                WHERE conversation.principal_id = ?
                GROUP BY conversation.conversation_id, conversation.created_at
                ORDER BY conversation.created_at DESC, conversation.conversation_id
                LIMIT ? OFFSET ?
                """,
                (principal_id, limit, offset),
            ).fetchall()
        return tuple(
            {
                "conversation_id": conversation_id,
                "created_at": created_at,
                "message_count": message_count,
            }
            for conversation_id, created_at, message_count in rows
        )

    def list_messages(
        self,
        conversation_id: str,
        principal_id: str,
        *,
        limit: int | None = None,
    ):
        if limit is not None and (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 200
        ):
            raise ValueError("limit must be None or an integer between 1 and 200.")

        with closing(self._connect()) as connection:
            owner = connection.execute(
                """
                SELECT principal_id FROM ai_conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            if owner is None or owner[0] != principal_id:
                raise ConversationNotFound("Conversation was not found.")
            if limit is None:
                rows = connection.execute(
                    """
                    SELECT role, content FROM ai_messages
                    WHERE conversation_id = ? ORDER BY id
                    """,
                    (conversation_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT role, content
                    FROM (
                        SELECT id, role, content FROM ai_messages
                        WHERE conversation_id = ?
                        ORDER BY id DESC LIMIT ?
                    )
                    ORDER BY id
                    """,
                    (conversation_id, limit),
                ).fetchall()
        return tuple((role, content) for role, content in rows)

    def append_exchange(
        self,
        conversation_id: str,
        principal_id: str,
        prompt: str,
        response: str,
    ) -> None:
        with closing(self._connect()) as connection:
            owner = connection.execute(
                """
                SELECT principal_id FROM ai_conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            if owner is None or owner[0] != principal_id:
                raise ConversationNotFound("Conversation was not found.")
            now = _utc_now_iso()
            connection.executemany(
                """
                INSERT INTO ai_messages (
                    conversation_id, role, content, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    (conversation_id, "user", prompt, now),
                    (conversation_id, "assistant", response, now),
                ),
            )
            connection.commit()

    def delete_conversation(self, conversation_id: str, principal_id: str) -> None:
        with closing(self._connect()) as connection:
            owner = connection.execute(
                """
                SELECT principal_id FROM ai_conversations
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            ).fetchone()
            if owner is None or owner[0] != principal_id:
                raise ConversationNotFound("Conversation was not found.")
            with connection:
                connection.execute(
                    "DELETE FROM ai_messages WHERE conversation_id = ?",
                    (conversation_id,),
                )
                connection.execute(
                    "DELETE FROM ai_conversations WHERE conversation_id = ?",
                    (conversation_id,),
                )
