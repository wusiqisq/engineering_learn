from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


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
    assert data["filename"] == "demo.md"
    assert data["chunk_count"] == 1
    assert data["chunks"][0]["index"] == 1
    assert "# Demo" in data["chunks"][0]["text"]


def test_upload_rejects_unsupported_file_type() -> None:
    response = client.post(
        "/documents",
        files={"file": ("demo.pdf", b"PDF content", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only .md and .txt files are supported"
