from app import embeddings


class FakeResponse:
    status_code = 200

    def json(self) -> dict:
        return {
            "data": [
                {"index": 1, "embedding": [0.0, 1.0]},
                {"index": 0, "embedding": [1.0, 0.0]},
            ]
        }


def test_openai_compatible_embeddings_are_returned_in_input_order(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("EMBEDDING_API_KEY", "test-key")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("EMBEDDING_MODEL", "embed-test")
    monkeypatch.setattr(embeddings.httpx, "post", fake_post)

    result = embeddings.embed_texts_openai_compatible(["first", "second"])

    assert result == [[1.0, 0.0], [0.0, 1.0]]
    assert captured["url"] == "https://example.test/v1/embeddings"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"] == {"model": "embed-test", "input": ["first", "second"]}
