"""Разбор вызовов функций прямо из текста ответа модели.

Основной формат:
    <tool_call>{"name": "get_weather", "arguments": {"city": "Париж"}}</tool_call>

Слабые модели часто отклоняются от формата, поэтому парсер терпим к:
  * незакрытому тегу (генерация обрывается на stop-последовательности);
  * ```json-ограждениям, одинарным кавычкам, Python-литералам;
  * ключам "parameters"/"args" вместо "arguments" и аргументам на верхнем уровне;
  * «голому» JSON без тегов, если в нём name известного инструмента.
"""
import ast
import json
import re
from dataclasses import dataclass

TAG_RE = re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.S)
FENCE_RE = re.compile(r"```(?:json)?", re.I)


@dataclass
class ToolCall:
    name: str
    arguments: dict

    def as_text(self) -> str:
        payload = json.dumps({"name": self.name, "arguments": self.arguments}, ensure_ascii=False)
        return f"<tool_call>{payload}</tool_call>"


def _first_object(text: str) -> str | None:
    """Первый сбалансированный {...} с учётом строк."""
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, quote, escaped = 0, False, "", False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_str = False
        elif ch in "\"'":
            in_str, quote = True, ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _loads(text: str) -> dict:
    body = _first_object(FENCE_RE.sub("", text))
    if body is None:
        raise ValueError("в вызове нет JSON-объекта")
    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        try:
            obj = ast.literal_eval(body.replace("true", "True").replace("false", "False").replace("null", "None"))
        except (ValueError, SyntaxError):
            raise ValueError(f"невалидный JSON: {body[:200]}") from None
    if not isinstance(obj, dict):
        raise ValueError("вызов должен быть JSON-объектом")
    return obj


def _to_call(obj: dict) -> ToolCall:
    if isinstance(obj.get("function"), dict):  # OpenAI-стиль {"function": {...}}
        obj = obj["function"]
    name = obj.get("name") or obj.get("tool") or obj.get("function")
    if not isinstance(name, str) or not name:
        raise ValueError('в вызове нет поля "name"')
    args = next((obj[k] for k in ("arguments", "args", "parameters", "params") if k in obj), None)
    if args is None:  # {"name": "get_weather", "city": "Париж"}
        args = {k: v for k, v in obj.items() if k not in ("name", "tool", "function")}
    if isinstance(args, str):
        args = _loads(args) if args.strip() else {}
    if not isinstance(args, dict):
        raise ValueError('"arguments" должен быть объектом')
    return ToolCall(name=name.strip(), arguments=args)


def parse_tool_calls(text: str, known: set[str]) -> tuple[list[ToolCall], list[str]]:
    """Возвращает (вызовы, ошибки разбора). Пустые оба списка — это обычный ответ."""
    calls, errors = [], []
    bodies = TAG_RE.findall(text)
    if not bodies:
        try:
            call = _to_call(_loads(text))
        except ValueError:
            return [], []
        return ([call], []) if call.name in known else ([], [])
    for body in bodies:
        try:
            calls.append(_to_call(_loads(body)))
        except ValueError as e:
            errors.append(str(e))
    return calls, errors


PLAN_RE = re.compile(r"^\s*План:\s*(.*)$", re.M | re.I)


def parse_plan(text: str, known: set[str]) -> list[str] | None:
    """Строка «План: a, b» -> ["a", "b"]; «План: без инструментов» -> []; нет строки -> None."""
    m = PLAN_RE.search(text)
    if not m:
        return None
    return [name for name in re.split(r"[,;\s→>]+", m.group(1)) if name in known]


def strip_tool_markup(text: str) -> str:
    text = PLAN_RE.sub("", TAG_RE.sub("", text))
    return text.replace("</tool_call>", "").strip()
