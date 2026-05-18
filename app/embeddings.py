import hashlib
import math
import os
import re

import httpx
from dotenv import load_dotenv

EMBEDDING_DIMENSION = 128
DEFAULT_EMBEDDING_BASE_URL = "https://api.openai.com/v1"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


class EmbeddingConfigError(RuntimeError):
    pass


class EmbeddingAPIError(RuntimeError):
    pass


def embed_texts(texts: list[str]) -> list[list[float]]:
    load_dotenv()
    provider = os.getenv("EMBEDDING_PROVIDER", "hash").lower()
    if provider in {"hash", "local"}:
        return embed_texts_hash(texts)
    if provider in {"openai", "openai-compatible", "compatible"}:
        return embed_texts_openai_compatible(texts)

    raise EmbeddingConfigError(f"Unsupported EMBEDDING_PROVIDER: {provider}")


def embed_texts_hash(texts: list[str]) -> list[list[float]]:
    return [_normalize(_hash_text(text)) for text in texts]


def embed_texts_openai_compatible(texts: list[str]) -> list[list[float]]:
    api_key = os.getenv("EMBEDDING_API_KEY")
    if not api_key:
        raise EmbeddingConfigError("EMBEDDING_API_KEY is not configured")

    base_url = os.getenv("EMBEDDING_BASE_URL", DEFAULT_EMBEDDING_BASE_URL).rstrip("/")
    model = os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)

    response = httpx.post(
        f"{base_url}/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": texts,
        },
        timeout=60,
    )
    if response.status_code >= 400:
        raise EmbeddingAPIError(f"Embedding API error {response.status_code}: {response.text}")

    data = response.json()
    try:
        embeddings = sorted(data["data"], key=lambda item: item["index"])
        return [[float(value) for value in item["embedding"]] for item in embeddings]
    except (KeyError, TypeError) as exc:
        raise EmbeddingAPIError("Embedding API returned an unexpected response") from exc


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0

    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def _hash_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return vector


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.lower())


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
