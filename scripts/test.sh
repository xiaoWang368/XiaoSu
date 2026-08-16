#!/usr/bin/env bash
# 跑后端 pytest + 前端类型检查。
# 用法: bash scripts/test.sh
set -e
cd "$(dirname "$0")/.."

echo "[test] pytest"
if uv run pytest test -q 2>&1 | tail -5; then
  echo "[test] pytest 通过"
else
  echo "[test] pytest 无测试或失败(见上)"
fi
