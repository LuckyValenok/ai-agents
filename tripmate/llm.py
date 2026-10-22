"""Тонкая обёртка над OpenAI-совместимым chat completions API со стримингом.

Параметр `tools` намеренно НЕ используется: вызовы функций агент
разбирает из текста ответа сам (см. parser.py).
"""
from collections.abc import Iterator

from openai import OpenAI

from .config import ModelSpec

_clients: dict[str, OpenAI] = {}


def client_for(spec: ModelSpec) -> OpenAI:
    if spec.key not in _clients:
        _clients[spec.key] = OpenAI(
            base_url=spec.base_url,
            api_key=spec.api_key,
            default_headers=spec.headers or None,
            timeout=120,
        )
    return _clients[spec.key]


def stream_chat(
    spec: ModelSpec,
    messages: list[dict],
    *,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    stop: list[str] | None = None,
) -> Iterator[str]:
    """Отдаёт ответ модели по кусочкам по мере генерации."""
    stream = client_for(spec).chat.completions.create(
        model=spec.model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stop=stop,
        stream=True,
    )
    with stream:
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
