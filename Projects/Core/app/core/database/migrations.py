import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path


Migration = Callable[[sqlite3.Connection], None]


def _create_auth_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS principals (
            principal_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            scheme TEXT NOT NULL,
            salt BLOB NOT NULL,
            digest BLOB NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (principal_id) REFERENCES principals(principal_id)
        )
        """
    )


def _create_audit_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            occurred_at TEXT NOT NULL,
            principal_id TEXT,
            key_id TEXT,
            event_type TEXT NOT NULL,
            outcome TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL
        )
        """
    )


def _create_paper_orders_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity TEXT NOT NULL,
            price TEXT NOT NULL,
            status TEXT NOT NULL
        )
        """
    )


def _create_ai_conversation_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_conversations (
            conversation_id TEXT PRIMARY KEY,
            principal_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def _create_ai_rate_limit_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_request_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_request_events_principal_time
        ON ai_request_events (principal_id, occurred_at)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id)
                REFERENCES ai_conversations(conversation_id)
        )
        """
    )


_MIGRATIONS: dict[str, tuple[tuple[int, str, Migration], ...]] = {
    "auth": ((1, "create_auth_tables", _create_auth_tables),),
    "audit": ((1, "create_audit_table", _create_audit_table),),
    "paper_orders": ((1, "create_paper_orders_table", _create_paper_orders_table),),
    "ai": (
        (1, "create_ai_conversation_tables", _create_ai_conversation_tables),
        (2, "create_ai_rate_limit_table", _create_ai_rate_limit_table),
    ),
}


def _ensure_migration_table(connection: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(schema_migrations)")
    }
    if columns and "component" not in columns:
        connection.execute("DROP TABLE schema_migrations")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            component TEXT NOT NULL,
            version INTEGER NOT NULL,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (component, version)
        )
        """
    )


def migrate_database(database_path, component: str) -> int:
    try:
        migrations = _MIGRATIONS[component]
    except KeyError as error:
        raise ValueError(f"Unknown database component: {component!r}.") from error

    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            _ensure_migration_table(connection)
            applied = {
                row[0]
                for row in connection.execute(
                    "SELECT version FROM schema_migrations WHERE component = ?",
                    (component,),
                )
            }
            for version, name, migration in migrations:
                if version in applied:
                    continue
                migration(connection)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (component, version, name)
                    VALUES (?, ?, ?)
                    """,
                    (component, version, name),
                )

    return migrations[-1][0]


def current_schema_version(database_path, component: str) -> int:
    if component not in _MIGRATIONS:
        raise ValueError(f"Unknown database component: {component!r}.")

    path = Path(database_path)
    if not path.exists():
        return 0

    with closing(sqlite3.connect(path)) as connection:
        exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'schema_migrations'
            """
        ).fetchone()
        if exists is None:
            return 0
        row = connection.execute(
            """
            SELECT COALESCE(MAX(version), 0)
            FROM schema_migrations
            WHERE component = ?
            """,
            (component,),
        ).fetchone()
        return row[0]
