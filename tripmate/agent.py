"""Агент: чат + вызовы функций, разобранные из текста ответа.

Цикл одного вопроса:
  1. модель генерирует ответ (генерация останавливается на </tool_call>);
  2. если в тексте есть вызов — выполняем функцию и отправляем результат
     обратно сообщением с <tool_result>, переходим к п.1;
  3. если вызова нет — это финальный ответ пользователю.
"""
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .config import ModelSpec
from .llm import stream_chat
from .parser import ToolCall, parse_plan, parse_tool_calls, strip_tool_markup
from .prompts import PromptVariant, progress_text
from .tools import TOOLS, execute

# Останавливаемся сразу после вызова — модель не успевает «додумать» результат сама.
STOP = ["</tool_call>", "<tool_result", "\nСистема:", "\nПользователь:", "\nПлан:"]
FORMAT_HELP = 'Формат вызова: <tool_call>{"name": "...", "arguments": {...}}</tool_call>'


@dataclass
class Step:
    raw: str
    calls: list[ToolCall] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    seconds: float = 0.0


@dataclass
class AgentReply:
    answer: str
    steps: list[Step]

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [c for s in self.steps for c in s.calls]


class Agent:
    def __init__(
        self,
        spec: ModelSpec,
        prompt: PromptVariant,
        *,
        temperature: float = 0.2,
        max_steps: int = 5,
        on_token: Callable[[str], None] | None = None,
        on_tool: Callable[[ToolCall, dict], None] | None = None,
    ):
        self.spec, self.prompt = spec, prompt
        self.temperature, self.max_steps = temperature, max_steps
        self.on_token, self.on_tool = on_token, on_tool
        self.reset()

    def reset(self) -> None:
        self.messages = self.prompt.initial_messages()

    def _generate(self) -> str:
        parts = []
        for token in stream_chat(self.spec, self.messages, temperature=self.temperature, stop=STOP):
            parts.append(token)
            if self.on_token:
                self.on_token(token)
        return "".join(parts)

    def ask(self, user_text: str) -> AgentReply:
        self.messages.append({"role": "user", "content": user_text})
        steps: list[Step] = []
        plan: list[str] | None = None
        done: list[str] = []
        nudged = False

        for _ in range(self.max_steps):
            started = time.perf_counter()
            raw = self._generate()
            calls, errors = parse_tool_calls(raw, set(TOOLS))
            step = Step(raw=raw, calls=calls, parse_errors=errors, seconds=time.perf_counter() - started)
            steps.append(step)
            if self.prompt.uses_plan and plan is None:
                plan = parse_plan(raw, set(TOOLS))

            if not calls and not errors:
                remaining = [t for t in plan or [] if t not in done]
                if remaining and not nudged:
                    # Модель пытается ответить, не выполнив собственный план — один раз возвращаем её к плану.
                    nudged = True
                    self.messages.append({"role": "assistant", "content": raw})
                    self.messages.append({"role": "user", "content":
                                          f"По твоему плану ещё нужно вызвать: {', '.join(remaining)}. "
                                          "Не отвечай по памяти — вызови инструмент."})
                    continue
                answer = strip_tool_markup(raw)
                self.messages.append({"role": "assistant", "content": answer})
                return AgentReply(answer=answer, steps=steps)

            # В историю кладём канонический вызов — модель видит правильный формат.
            prefix = raw.split("<tool_call>")[0].strip() if "<tool_call>" in raw else ""
            canonical = "\n".join([prefix, *(c.as_text() for c in calls)]).strip() or raw
            self.messages.append({"role": "assistant", "content": canonical})

            results: list[tuple[str, dict]] = []
            for call in calls:
                result = execute(call.name, call.arguments)
                step.results.append(result)
                results.append((call.name, result))
                if self.on_tool:
                    self.on_tool(call, result)
            for err in errors:
                results.append(("parse_error", {"error": f"не удалось разобрать вызов: {err}. {FORMAT_HELP}"}))
            done.extend(c.name for c in calls)
            progress = progress_text(plan, done) if self.prompt.uses_plan else ""
            self.messages.append({"role": "user", "content": self.prompt.tool_results_message(results, user_text, progress)})

        # Модель зациклилась на вызовах — просим ответить тем, что есть.
        self.messages.append({"role": "user", "content": "Лимит вызовов исчерпан. Дай финальный ответ без инструментов."})
        raw = self._generate()
        steps.append(Step(raw=raw))
        answer = strip_tool_markup(raw)
        self.messages.append({"role": "assistant", "content": answer})
        return AgentReply(answer=answer, steps=steps)
