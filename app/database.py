import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data/rag_project.db"


def init_database(db_path: Path = DEFAULT_DATABASE_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL,
                chunk_count INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                char_count INTEGER NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                ON chunks (document_id);
            """
        )


def save_document(filename: str, chunks: list[str], db_path: Path = DEFAULT_DATABASE_PATH) -> dict[str, Any]:
    created_at = datetime.now(UTC).isoformat()
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (filename, created_at, chunk_count)
            VALUES (?, ?, ?)
            """,
            (filename, created_at, len(chunks)),
        )
        document_id = cursor.lastrowid
        connection.executemany(
            """
            INSERT INTO chunks (document_id, chunk_index, text, char_count)
            VALUES (?, ?, ?, ?)
            """,
            [
                (document_id, index, chunk, len(chunk))
                for index, chunk in enumerate(chunks, start=1)
            ],
        )

    document = get_document(document_id, db_path)
    if document is None:
        raise RuntimeError("Saved document could not be loaded")
    return document


def list_documents(db_path: Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, filename, created_at, chunk_count
            FROM documents
            ORDER BY id DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_document(document_id: int, db_path: Path = DEFAULT_DATABASE_PATH) -> dict[str, Any] | None:
    with _connect(db_path) as connection:
        document_row = connection.execute(
            """
            SELECT id, filename, created_at, chunk_count
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

    if document_row is None:
        return None

    document = dict(document_row)
    document["chunks"] = list_chunks(document_id, db_path)
    return document


def list_chunks(document_id: int, db_path: Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, chunk_index AS 'index', text, char_count
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
