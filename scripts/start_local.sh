#!/usr/bin/env bash
# Поднимает llama-server (OpenAI-совместимый API) на локальных моделях:
#   ДЗ 1 — сырой текст, вызовы инструментов разбираем сами:
#     qwen2.5-3b-instruct   -> http://127.0.0.1:8081/v1
#     llama-3.2-3b-instruct -> http://127.0.0.1:8082/v1
#   ДЗ 2 — обычный режим, нужен structured output (response_format: json_schema):
#     qwen2.5-3b-instruct   -> http://127.0.0.1:8083/v1
# Остановить: scripts/stop_local.sh
#
# --skip-chat-parsing: иначе сервер сам вырезает <tool_call> из ответа (встроенный tool calling),
# а по заданию ДЗ 1 вызовы нужно разбирать из текста самим. Но этот же флаг отключает
# JSON-грамматику для response_format, поэтому для ДЗ 2 поднят отдельный сервер без него.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs

start() {
  local name=$1 port=$2 model=$3; shift 3
  if curl -sf "http://127.0.0.1:$port/health" >/dev/null; then
    echo "$name уже запущен на :$port"; return
  fi
  llama-server -m "models/$model" --alias "${name%%@*}" --port "$port" \
    -c 8192 -ngl 99 "$@" >"logs/server-$name.log" 2>&1 &
  echo $! >"logs/server-$name.pid"
  echo "$name -> :$port (pid $!)"
}

start qwen2.5-3b-instruct       8081 qwen2.5-3b-instruct-q4_k_m.gguf --skip-chat-parsing
start llama-3.2-3b-instruct     8082 llama-3.2-3b-instruct-q4_k_m.gguf --skip-chat-parsing
start qwen2.5-3b-instruct@json  8083 qwen2.5-3b-instruct-q4_k_m.gguf

for port in 8081 8082 8083; do
  until curl -sf "http://127.0.0.1:$port/health" >/dev/null; do sleep 1; done
done
echo "Серверы готовы."
