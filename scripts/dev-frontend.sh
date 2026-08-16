#!/usr/bin/env bash
# 只起前端。用法: bash scripts/dev-frontend.sh
set -e
cd "$(dirname "$0")/../frontend"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
pnpm dev -p "$FRONTEND_PORT"
