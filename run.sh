#!/usr/bin/env bash
# X Trends Dashboard 起動スクリプト
set -euo pipefail
cd "$(dirname "$0")"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

if [ ! -d .venv ]; then
  echo "[setup] 仮想環境を作ります…"
  python3 -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "[setup] .env が見つからないので .env.example から作成します（デモモードで起動）"
  cp .env.example .env
fi

echo "[run] http://${HOST}:${PORT}  (API docs: /docs)"
exec ./.venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT" "${@}"
