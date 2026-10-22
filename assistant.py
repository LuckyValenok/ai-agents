"""Задание 4: TripMate — ассистент путешественника с вызовом функций из текста ответа.

    uv run assistant.py --model qwen --prompt v5

Команды: /reset — очистить историю, /exit — выход (также Ctrl+D).
"""
import argparse
import json
import readline  # noqa: F401

import openai

from tripmate.agent import Agent
from tripmate.config import MODEL_KEYS, get_model
from tripmate.prompts import PROMPTS

CYAN, RESET = "\033[36m", "\033[0m"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", choices=MODEL_KEYS, default="qwen")
    ap.add_argument("--prompt", choices=PROMPTS, default="v5")
    args = ap.parse_args()

    spec = get_model(args.model)

    def on_token(token: str) -> None:
        print(token, end="", flush=True)

    def on_tool(call, result) -> None:
        args_text = json.dumps(call.arguments, ensure_ascii=False)
        print(f"\n{CYAN}  ⚙ {call.name}({args_text}) → {json.dumps(result, ensure_ascii=False)[:300]}{RESET}")
        print("bot> ", end="", flush=True)

    agent = Agent(spec, PROMPTS[args.prompt], on_token=on_token, on_tool=on_tool)
    print(f"TripMate на {spec.label}, промпт {args.prompt}. /reset — очистить историю, /exit — выход.\n")

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
            agent.reset()
            print("(история очищена)\n")
            continue
        print("bot> ", end="", flush=True)
        try:
            agent.ask(line)
        except KeyboardInterrupt:
            print(" [прервано, история сброшена]", end="")
            agent.reset()
        except openai.APIError as e:
            print(f"\n[ошибка API: {e}]", end="")
        print("\n")

    print("Хорошей поездки!")


if __name__ == "__main__":
    main()
