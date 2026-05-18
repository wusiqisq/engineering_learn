import sqlite3
import json
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
                embedding TEXT,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                ON chunks (document_id);
            """
        )
        _ensure_chunk_embedding_column(connection)


def save_document(
    filename: str,
    chunks: list[str],
    embeddings: list[list[float]] | None = None,
    db_path: Path = DEFAULT_DATABASE_PATH,
) -> dict[str, Any]:
    if embeddings is not None and len(chunks) != len(embeddings):
        raise ValueError("Each chunk must have one embedding")

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
            INSERT INTO chunks (document_id, chunk_index, text, char_count, embedding)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    document_id,
                    index,
                    chunk,
                    len(chunk),
                    serialize_embedding(embeddings[index - 1]) if embeddings is not None else None,
                )
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


def list_chunks_missing_embeddings(db_path: Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, text
            FROM chunks
            WHERE embedding IS NULL
            ORDER BY id ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def update_chunk_embedding(chunk_id: int, embedding: list[float], db_path: Path = DEFAULT_DATABASE_PATH) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            UPDATE chunks
            SET embedding = ?
            WHERE id = ?
            """,
            (serialize_embedding(embedding), chunk_id),
        )


def list_searchable_chunks(db_path: Path = DEFAULT_DATABASE_PATH) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                chunks.id AS chunk_id,
                chunks.document_id,
                documents.filename,
                chunks.chunk_index AS 'index',
                chunks.text,
                chunks.char_count,
                chunks.embedding
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            WHERE chunks.embedding IS NOT NULL
            ORDER BY chunks.id ASC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def serialize_embedding(embedding: list[float]) -> str:
    return json.dumps([float(value) for value in embedding])


def deserialize_embedding(raw_embedding: str) -> list[float]:
    return [float(value) for value in json.loads(raw_embedding)]


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _ensure_chunk_embedding_column(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(chunks)").fetchall()
    column_names = {column["name"] for column in columns}
    if "embedding" not in column_names:
        connection.execute("ALTER TABLE chunks ADD COLUMN embedding TEXT")
