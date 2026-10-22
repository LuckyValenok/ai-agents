#!/usr/bin/env bash
cd "$(dirname "$0")/.."
for pidfile in logs/server-*.pid; do
  [ -f "$pidfile" ] || continue
  kill "$(cat "$pidfile")" 2>/dev/null && echo "остановлен $(basename "$pidfile" .pid)"
  rm -f "$pidfile"
done
