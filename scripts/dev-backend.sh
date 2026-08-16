#!/usr/bin/env bash
# 只起后端相关(docker + 后端 + mock + 钉钉 worker),前端单独用 dev-frontend.sh
set -e
cd "$(dirname "$0")/.."
LOG_DIR=logs
mkdir -p "$LOG_DIR"
BACKEND_PORT="${BACKEND_PORT:-8000}"
MOCK_PORT="${MOCK_PORT:-8001}"

docker compose up -d postgres minio
uv run uvicorn server.app:app --host 127.0.0.1 --port "$BACKEND_PORT" > "$LOG_DIR/backend.log" 2>&1 &
B=$!
uv run uvicorn mock_api.app:app --host 127.0.0.1 --port "$MOCK_PORT" > "$LOG_DIR/mock.log" 2>&1 &
M=$!
uv run python -m im.worker > "$LOG_DIR/dingtalk.log" 2>&1 &
W=$!
trap 'kill $B $M $W 2>/dev/null' EXIT INT TERM
echo "后端:$BACKEND_PORT mock:$MOCK_PORT 钉钉worker(日志 $LOG_DIR/) Ctrl+C 停止"
wait
