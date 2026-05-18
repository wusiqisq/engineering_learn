import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import (  # noqa: E402
    DEFAULT_DATABASE_PATH,
    init_database,
    list_all_chunks,
    list_chunks_missing_embeddings,
    update_chunk_embedding,
)
from app.embeddings import embed_texts  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild chunk embeddings.")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--missing-only", action="store_true")
    args = parser.parse_args()

    init_database(DEFAULT_DATABASE_PATH)
    chunks = list_chunks_missing_embeddings(DEFAULT_DATABASE_PATH) if args.missing_only else list_all_chunks(DEFAULT_DATABASE_PATH)
    if not chunks:
        print("No chunks need embeddings.")
        return

    print(f"Rebuilding embeddings for {len(chunks)} chunks...")
    for start in range(0, len(chunks), args.batch_size):
        batch = chunks[start : start + args.batch_size]
        embeddings = embed_texts([chunk["text"] for chunk in batch])
        for chunk, embedding in zip(batch, embeddings, strict=True):
            update_chunk_embedding(chunk["id"], embedding, DEFAULT_DATABASE_PATH)
        print(f"Updated {min(start + len(batch), len(chunks))}/{len(chunks)}")

    print("Done.")


if __name__ == "__main__":
    main()
