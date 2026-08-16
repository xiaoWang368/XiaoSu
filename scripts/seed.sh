#!/usr/bin/env bash
# 清空并重灌种子知识库。用法: bash scripts/seed.sh [目录,默认 data/seed]
set -e
cd "$(dirname "$0")/.."
SEED_DIR="${1:-data/seed}"

echo "[seed] 清空并从 $SEED_DIR 重灌"
uv run python - "$SEED_DIR" <<'PYEOF'
import sys
from pathlib import Path

import processor.db as db
from processor.import_processor.ingest import import_document
from utils.chroma_utils import delete_by_filter, get_or_create_collection

db.init_db()
coll = get_or_create_collection()
coll.delete(where={"doc_id": {"$ne": "__none__"}})
for d in db.list_documents():
    try:
        delete_by_filter({"doc_id": d["id"]})
    except Exception:
        pass
    db.delete_document(d["id"])

src = Path(sys.argv[1])
exts = {".md", ".txt", ".pdf", ".docx"}
for f in sorted(src.iterdir()):
    if f.is_file() and f.suffix.lower() in exts:
        try:
            r = import_document(f.name, f.read_bytes())
            print(f"  {f.name} -> {r.get('chunk_count')} chunks")
        except Exception as e:  # noqa: BLE001
            print(f"  {f.name} FAIL {str(e)[:60]}")
print("Chroma total:", coll.count())
PYEOF
