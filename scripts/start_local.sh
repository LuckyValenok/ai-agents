#!/usr/bin/env bash
# Поднимает два llama-server (OpenAI-совместимый API) на локальных моделях:
#   qwen2.5-3b-instruct  -> http://127.0.0.1:8081/v1
#   llama-3.2-3b-instruct -> http://127.0.0.1:8082/v1
# Остановить: scripts/stop_local.sh
# --skip-chat-parsing: иначе сервер сам вырезает <tool_call> из ответа (встроенный tool calling),
# а по заданию вызовы нужно разбирать из текста самим.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs

start() {
  local name=$1 port=$2 model=$3
  if curl -sf "http://127.0.0.1:$port/health" >/dev/null; then
    echo "$name уже запущен на :$port"; return
  fi
  llama-server -m "models/$model" --alias "$name" --port "$port" \
    -c 8192 -ngl 99 --skip-chat-parsing >"logs/server-$name.log" 2>&1 &
  echo $! >"logs/server-$name.pid"
  echo "$name -> :$port (pid $!)"
}

start qwen2.5-3b-instruct  8081 qwen2.5-3b-instruct-q4_k_m.gguf
start llama-3.2-3b-instruct 8082 llama-3.2-3b-instruct-q4_k_m.gguf

for port in 8081 8082; do
  until curl -sf "http://127.0.0.1:$port/health" >/dev/null; do sleep 1; done
done
echo "Оба сервера готовы."
