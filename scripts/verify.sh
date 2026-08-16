#!/usr/bin/env bash
# 约束审计:单文件≤500行 / 单目录≤8文件 / 禁commonjs / .env不入库。
# 用法: bash scripts/verify.sh
set -e
cd "$(dirname "$0")/.."
FAIL=0

echo "[verify] 后端单文件 ≤500 行"
while IFS= read -r f; do
  lines=$(wc -l < "$f")
  if [ "$lines" -gt 500 ]; then
    echo "  !! $f ($lines 行)"; FAIL=1
  fi
done < <(find processor im server mock_api -name "*.py" -not -path "*/__pycache__/*")

echo "[verify] 单目录文件数 ≤8(后端源码目录)"
for d in processor processor/query_processor processor/query_processor/nodes processor/query_processor/prompt \
         processor/import_processor processor/import_processor/nodes im im/channels server server/routes mock_api; do
  [ -d "$d" ] || continue
  c=$(find "$d" -maxdepth 1 -type f -name "*.py" | wc -l)
  if [ "$c" -gt 8 ]; then echo "  !! $d ($c 文件)"; FAIL=1; fi
done

echo "[verify] 前端禁 commonjs(require)"
if grep -rn "require(" frontend --include="*.ts" --include="*.tsx" --include="*.mjs" 2>/dev/null \
   | grep -v node_modules | grep -v "/.next/" | grep -v "next-env"; then
  echo "  !! 发现 require("; FAIL=1
else
  echo "  OK"
fi

echo "[verify] .env 不入库"
if git ls-files .env 2>/dev/null | grep -q "^.env$"; then
  echo "  !! .env 被跟踪!"; FAIL=1
else
  echo "  OK"
fi

[ "$FAIL" -eq 0 ] && echo "verify 全部通过 ✅" || echo "verify 有违规项 ❌"
exit $FAIL
