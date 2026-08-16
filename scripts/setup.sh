#!/usr/bin/env bash
# 初始化环境:依赖 + .env + 目录。用法: bash scripts/setup.sh
set -e
cd "$(dirname "$0")/.."

echo "[setup] uv sync(后端依赖)"
uv sync

echo "[setup] 前端依赖(pnpm)"
cd frontend && pnpm install && cd ..

if [ ! -f .env ]; then
  echo "[setup] 复制 .env.example -> .env(请填入 DASHSCOPE_API_KEY / DINGTALK_APP_KEY/SECRET / MINERU_API_TOKEN)"
  cp .env.example .env
else
  echo "[setup] .env 已存在,跳过"
fi

mkdir -p data/uploads data/chroma data/seed logs
echo "[setup] 完成。启动: bash scripts/start.sh"
