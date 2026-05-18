from app.chunking import chunk_text


def test_chunk_text_splits_markdown_by_blocks() -> None:
    text = "# Title\n\nFirst paragraph.\n\nSecond paragraph."

    chunks = chunk_text(text, max_chars=30)

    assert chunks == ["# Title\n\nFirst paragraph.", "Second paragraph."]


def test_chunk_text_returns_empty_list_for_blank_text() -> None:
    assert chunk_text(" \n\n ") == []
