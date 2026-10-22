"""Модели, с которыми умеет работать проект.

Все они доступны через OpenAI-совместимый API:
  * qwen / llama — локальные llama-server (llama.cpp);
  * openrouter   — облачная модель-эталон.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()


@dataclass(frozen=True)
class ModelSpec:
    key: str
    base_url: str
    model: str
    api_key: str
    headers: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.key} ({self.model})"


MODEL_KEYS = ("qwen", "llama", "openrouter")


def get_model(key: str) -> ModelSpec:
    if key == "qwen":
        return ModelSpec(
            key="qwen",
            base_url=os.getenv("QWEN_URL", "http://127.0.0.1:8081/v1"),
            model="qwen2.5-3b-instruct",
            api_key="local",
        )
    if key == "llama":
        return ModelSpec(
            key="llama",
            base_url=os.getenv("LLAMA_URL", "http://127.0.0.1:8082/v1"),
            model="llama-3.2-3b-instruct",
            api_key="local",
        )
    if key == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise SystemExit("Нет OPENROUTER_API_KEY: скопируйте .env.example в .env и вставьте ключ.")
        return ModelSpec(
            key="openrouter",
            base_url="https://openrouter.ai/api/v1",
            model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            api_key=api_key,
            headers={"X-Title": "TripMate homework"},
        )
    raise SystemExit(f"Неизвестная модель {key!r}. Доступны: {', '.join(MODEL_KEYS)}")
