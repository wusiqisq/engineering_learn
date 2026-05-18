import os
from typing import Any

import httpx
from dotenv import load_dotenv


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"


class DeepSeekConfigError(RuntimeError):
    pass


class DeepSeekAPIError(RuntimeError):
    pass


def generate_answer(question: str, sources: list[dict[str, Any]]) -> str:
    load_dotenv()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise DeepSeekConfigError("DEEPSEEK_API_KEY is not configured")

    base_url = os.getenv("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL).rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", DEEPSEEK_MODEL)

    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": _build_messages(question, sources),
            "temperature": 0.2,
            "max_tokens": 800,
        },
        timeout=60,
    )

    if response.status_code >= 400:
        raise DeepSeekAPIError(f"DeepSeek API error {response.status_code}: {response.text}")

    data = response.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekAPIError("DeepSeek API returned an unexpected response") from exc


def _build_messages(question: str, sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    context = "\n\n".join(
        (
            f"[{source['citation']}] 文件：{source['filename']} / "
            f"分块：{source['index']} / 相似度：{source['score']}\n{source['text']}"
        )
        for source in sources
    )

    return [
        {
            "role": "system",
            "content": (
                "你是一个 RAG 问答助手。只能根据提供的资料回答问题。"
                "如果资料不足以回答，就明确说资料中没有足够信息。"
                "回答要简洁。凡是使用资料中的信息，必须在相关句子后标注资料编号，格式如 [1]、[2]。"
            ),
        },
        {
            "role": "user",
            "content": f"资料：\n{context}\n\n问题：{question}",
        },
    ]
