"""Задания 4.1 и 4.2: прогон ассистента по набору сценариев с логами.

    uv run evaluate.py                                  # qwen и llama, все промпты v1…v5
    uv run evaluate.py --models qwen llama openrouter --prompts v2

На каждую пару (модель, промпт) пишется отдельный logs/<модель>__<промпт>.log
с полной трассой: сырые ответы модели, вызовы, результаты, финальный ответ,
автоматические проверки. Сводная таблица — logs/summary.md.
"""
import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import datetime

import openai

from tripmate.agent import Agent
from tripmate.config import MODEL_KEYS, ROOT, get_model
from tripmate.prompts import PROMPTS

LOGS = ROOT / "logs"


@dataclass
class Scenario:
    id: str
    question: str
    tools: set[str]                      # какие инструменты обязаны быть вызваны (пусто — никакие)
    contains: list[list[str]] = field(default_factory=list)  # из КАЖДОЙ группы в ответе есть хотя бы одна строка
    forbid: list[str] = field(default_factory=list)          # признаки выдуманных данных
    note: str = ""


SCENARIOS = [
    Scenario("weather", "Какая сейчас погода в Париже?", {"get_weather"}, [["14"]]),
    Scenario("time", "Который час сейчас в Токио?", {"get_local_time"}, [[":"]]),
    Scenario("currency", "Сколько будет 150 евро в рублях?", {"convert_currency"},
             [["15045", "15 045", "15,045", "15.045"]]),
    Scenario("attractions", "Что обязательно посмотреть в Стамбуле?", {"get_attractions"},
             [["софи"], ["голуб", "базар", "босфор"]]),
    Scenario("flights", "Найди билеты из Москвы в Дубай", {"search_flights"},
             [["33800", "33 800", "41200", "41 200"]]),
    Scenario("smalltalk", "Привет! Расскажи в двух словах, что ты умеешь?", set(), note="инструменты не нужны"),
    Scenario("general", "Дай три совета, как не забыть ничего важного при сборе чемодана", set(),
             note="инструменты не нужны"),
    Scenario("multi_tool", "Собираюсь в Рим: какая там погода и что посмотреть?", {"get_weather", "get_attractions"},
             [["21"], ["колизей", "ватикан", "треви", "пантеон"]], note="вопрос из двух частей"),
    Scenario("unknown_city", "Какая погода в Урюпинске?", {"get_weather"},
             [["нет", "неизвест", "не известн", "не удалось", "недоступ", "отсутств", "не могу", "не нашёл", "не нашел"]],
             forbid=["°", "градус"], note="инструмент вернёт error — нельзя выдумывать погоду"),
    Scenario("chain", "У меня 300 долларов. Хватит на самый дешёвый билет из Москвы в Стамбул?",
             {"search_flights", "convert_currency"}, [["21400", "21 400"], ["хват"]],
             forbid=["не хват", "победа", "3 200", "3200"],
             note="2 шага: найти билет (21 400 ₽), перевести 300 USD (27 750 ₽) => хватит"),
]


def check(sc: Scenario, reply) -> dict[str, bool]:
    called = {c.name for c in reply.tool_calls}
    answer = reply.answer.lower()
    results = [r for s in reply.steps for r in s.results]
    checks = {
        "tools": sc.tools <= called if sc.tools else not called,
        "format": not any(s.parse_errors for s in reply.steps) and not any(
            "неизвестный инструмент" in str(r.get("error", "")) or "не хватает" in str(r.get("error", ""))
            for r in results),
        "answer": bool(answer) and "<tool" not in answer,
    }
    if sc.contains:
        checks["content"] = all(any(s in answer for s in group) for group in sc.contains)
    if sc.forbid:
        checks["no_hallucination"] = not any(s in answer for s in sc.forbid)
    return checks


def run(model_key: str, prompt_key: str) -> dict:
    spec = get_model(model_key)
    log_path = LOGS / f"{model_key}__{prompt_key}.log"
    passed = total = 0
    per_scenario = {}
    started = time.perf_counter()

    with log_path.open("w") as log:
        def w(text=""):
            log.write(text + "\n")
            log.flush()

        w(f"# model={spec.label} prompt={prompt_key} temperature=0 date={datetime.now():%Y-%m-%d %H:%M}")
        for sc in SCENARIOS:
            agent = Agent(spec, PROMPTS[prompt_key], temperature=0.0)
            w("\n" + "=" * 80)
            w(f"[{sc.id}] USER: {sc.question}")
            if sc.note:
                w(f"  note: {sc.note}")
            try:
                reply = agent.ask(sc.question)
            except openai.APIError as e:
                w(f"  !! API error: {e}")
                per_scenario[sc.id] = "ERR"
                total += 1
                continue
            for i, step in enumerate(reply.steps, 1):
                w(f"--- step {i} ({step.seconds:.1f}s) raw:")
                w(step.raw)
                for call, result in zip(step.calls, step.results):
                    w(f"  >> CALL {call.name}({json.dumps(call.arguments, ensure_ascii=False)})")
                    w(f"  << {json.dumps(result, ensure_ascii=False)}")
                for err in step.parse_errors:
                    w(f"  !! PARSE ERROR: {err}")
            w(f"FINAL: {reply.answer}")
            checks = check(sc, reply)
            ok = all(checks.values())
            passed += ok
            total += 1
            per_scenario[sc.id] = "✅" if ok else "❌"
            w(f"CHECKS: {' '.join(f'{k}={'ok' if v else 'FAIL'}' for k, v in checks.items())} => {'PASS' if ok else 'FAIL'}")
            print(f"  {model_key:<10} {prompt_key}  {sc.id:<13} {'PASS' if ok else 'FAIL'}  {checks}")

        w("\n" + "=" * 80)
        w(f"TOTAL: {passed}/{total} passed in {time.perf_counter() - started:.0f}s")

    return {"model": spec.label, "prompt": prompt_key, "passed": passed, "total": total,
            "scenarios": per_scenario, "log": log_path.name}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", choices=MODEL_KEYS, default=["qwen", "llama"])
    ap.add_argument("--prompts", nargs="+", choices=PROMPTS, default=list(PROMPTS))
    args = ap.parse_args()

    LOGS.mkdir(exist_ok=True)
    rows = [run(m, p) for m in args.models for p in args.prompts]

    header = "| модель | промпт | итог | " + " | ".join(s.id for s in SCENARIOS) + " | лог |"
    lines = [header, "|" + "---|" * (len(SCENARIOS) + 4)]
    for r in rows:
        cells = " | ".join(r["scenarios"].get(s.id, "—") for s in SCENARIOS)
        lines.append(f"| {r['model']} | {r['prompt']} | **{r['passed']}/{r['total']}** | {cells} | `{r['log']}` |")
    summary = "\n".join(lines)
    (LOGS / "summary.md").write_text(f"# Результаты прогона ({datetime.now():%Y-%m-%d %H:%M})\n\n{summary}\n")
    print("\n" + summary)


if __name__ == "__main__":
    main()
