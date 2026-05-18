from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.database import init_database
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def use_test_database(tmp_path: Path) -> None:
    app.state.database_path = tmp_path / "test.db"
    app.state.embed_texts = fake_embed_texts
    init_database(app.state.database_path)


def fake_embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings = []
    for text in texts:
        normalized = text.lower()
        embeddings.append(
            [
                float(normalized.count("python")),
                float(normalized.count("database") + normalized.count("sqlite")),
                float(normalized.count("rag")),
                1.0,
            ]
        )
    return embeddings


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_markdown_document_returns_chunks() -> None:
    response = client.post(
        "/documents",
        files={
            "file": (
                "demo.md",
                b"# Demo\n\nThis is the first paragraph.\n\nThis is the second paragraph.",
                "text/markdown",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["id"], int)
    assert data["filename"] == "demo.md"
    assert data["chunk_count"] == 1
    assert data["chunks"][0]["id"] >= 1
    assert data["chunks"][0]["index"] == 1
    assert "# Demo" in data["chunks"][0]["text"]


def test_upload_rejects_unsupported_file_type() -> None:
    response = client.post(
        "/documents",
        files={"file": ("demo.pdf", b"PDF content", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .md and .txt files are supported"


def test_list_documents_returns_saved_uploads() -> None:
    upload_response = client.post(
        "/documents",
        files={"file": ("notes.txt", b"First note.\n\nSecond note.", "text/plain")},
    )
    document_id = upload_response.json()["id"]

    list_response = client.get("/documents")

    assert list_response.status_code == 200
    documents = list_response.json()
    assert documents[0]["id"] == document_id
    assert documents[0]["filename"] == "notes.txt"
    assert documents[0]["chunk_count"] == 1


def test_get_document_detail_returns_chunks() -> None:
    upload_response = client.post(
        "/documents",
        files={"file": ("notes.md", b"# Notes\n\nSaved content.", "text/markdown")},
    )
    document_id = upload_response.json()["id"]

    detail_response = client.get(f"/documents/{document_id}")

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == document_id
    assert detail["chunks"][0]["text"] == "# Notes\n\nSaved content."


def test_get_missing_document_returns_404() -> None:
    response = client.get("/documents/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_search_returns_most_similar_chunks() -> None:
    content = f"{'Python testing notes. ' * 50}\n\n{'SQLite database storage notes. ' * 50}"
    client.post(
        "/documents",
        files={
            "file": (
                "notes.md",
                content.encode("utf-8"),
                "text/markdown",
            )
        },
    )

    response = client.post("/search", json={"query": "database", "top_k": 2})

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "database"
    assert len(data["results"]) == 2
    assert "SQLite database" in data["results"][0]["text"]
    assert data["results"][0]["score"] >= data["results"][1]["score"]


def test_search_rejects_blank_query() -> None:
    response = client.post("/search", json={"query": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"
