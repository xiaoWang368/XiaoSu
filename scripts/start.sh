#!/usr/bin/env bash
# 一条命令启动:基础设施(docker) + 后端 + mock + 钉钉 worker + 前端。
# 用法: bash scripts/start.sh    (Ctrl+C 全部停止)
set -e
cd "$(dirname "$0")/.."

LOG_DIR=logs
mkdir -p "$LOG_DIR"
BACKEND_PORT="${BACKEND_PORT:-8000}"
MOCK_PORT="${MOCK_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

echo "[start] 基础设施(docker: postgres + minio)"
docker compose up -d postgres minio

echo "[start] 后端 :$BACKEND_PORT"
uv run uvicorn server.app:app --host 127.0.0.1 --port "$BACKEND_PORT" > "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

echo "[start] mock :$MOCK_PORT"
uv run uvicorn mock_api.app:app --host 127.0.0.1 --port "$MOCK_PORT" > "$LOG_DIR/mock.log" 2>&1 &
MOCK_PID=$!

echo "[start] 钉钉 worker"
uv run python -m im.worker > "$LOG_DIR/dingtalk.log" 2>&1 &
WORKER_PID=$!

echo "[start] 前端 :$FRONTEND_PORT"
(cd frontend && pnpm dev -p "$FRONTEND_PORT") > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "[start] 停止全部服务…"
  kill "$BACKEND_PID" "$MOCK_PID" "$WORKER_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo ""
echo "=============================================="
echo "  小苏已启动"
echo "    前端 : http://localhost:$FRONTEND_PORT"
echo "    后端 : http://localhost:$BACKEND_PORT   (/api/docs /api/chat /doc/{id})"
echo "    钉钉 : 群 @小苏"
echo "    日志 : $LOG_DIR/"
echo "  按 Ctrl+C 停止全部"
echo "=============================================="

wait
