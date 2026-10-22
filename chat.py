"""Задание 3: простой REPL-чат в терминале.

    uv run chat.py --model qwen        # или llama / openrouter

Команды: /reset — очистить историю, /exit — выход (также Ctrl+D).
Ctrl+C во время ответа прерывает генерацию, но не выходит из чата.
"""
import argparse
import readline  # noqa: F401  — стрелки и история ввода в input()

import openai

from tripmate.config import MODEL_KEYS, get_model
from tripmate.llm import stream_chat

SYSTEM = "Ты — дружелюбный ассистент. Отвечай по-русски, кратко."


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=MODEL_KEYS, default="qwen")
    ap.add_argument("--system", default=SYSTEM, help="системный промпт")
    args = ap.parse_args()

    spec = get_model(args.model)
    history = [{"role": "system", "content": args.system}]
    print(f"Чат с {spec.label}. /reset — очистить историю, /exit — выход.\n")

    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/exit", "/quit"):
            break
        if line == "/reset":
            history = history[:1]
            print("(история очищена)\n")
            continue

        history.append({"role": "user", "content": line})
        print("bot> ", end="", flush=True)
        parts: list[str] = []
        try:
            for token in stream_chat(spec, history):
                print(token, end="", flush=True)
                parts.append(token)
        except KeyboardInterrupt:
            print(" [прервано]", end="")
        except openai.APIError as e:
            print(f"\n[ошибка API: {e}]")
            history.pop()
            continue
        print("\n")
        history.append({"role": "assistant", "content": "".join(parts)})

    print("Пока!")


if __name__ == "__main__":
    main()
