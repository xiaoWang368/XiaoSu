"""
PostgreSQL 数据层：documents / chunks / chat_logs / settings。

psycopg 同步 + 连接池。异步调用方(server 路由)用 asyncio.to_thread 包装；
LangGraph 节点(同步)直接调用。
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, List, Optional

from dotenv import load_dotenv
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()  # 读取 .env(与 config/*_config.py 一致)

_pool: Optional[ConnectionPool] = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        # postgres 连接串(原 settings.postgres_dsn 内联到此调用处)
        dsn = (
            f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
            f"port={os.getenv('POSTGRES_PORT', '5432')} "
            f"user={os.getenv('POSTGRES_USER', 'xiaosu')} "
            f"password={os.getenv('POSTGRES_PASSWORD', 'xiaosu')} "
            f"dbname={os.getenv('POSTGRES_DB', 'xiaosu')}"
        )
        _pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=5,
            open=False,
        )
        _pool.open()
    return _pool


@contextmanager
def conn() -> Iterator[Connection]:
    with _get_pool().connection() as c:
        c.row_factory = dict_row
        yield c


_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    ext         TEXT NOT NULL DEFAULT '',
    size        BIGINT NOT NULL DEFAULT 0,
    sha256      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | indexing | indexed | failed
    error       TEXT,
    chunk_count INT NOT NULL DEFAULT 0,
    minio_key   TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_name ON documents(name);

CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL,
    doc_name    TEXT NOT NULL DEFAULT '',
    chunk_index INT NOT NULL,
    char_start  INT NOT NULL DEFAULT 0,
    char_end    INT NOT NULL DEFAULT 0,
    text        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);

CREATE TABLE IF NOT EXISTS chat_logs (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL DEFAULT '',
    user_id     TEXT NOT NULL DEFAULT '',
    platform    TEXT NOT NULL DEFAULT '',
    question    TEXT NOT NULL DEFAULT '',
    answer      TEXT NOT NULL DEFAULT '',
    tools_used  JSONB,
    citations   JSONB,
    tokens      JSONB,
    refused     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_logs_created ON chat_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_logs_user ON chat_logs(user_id);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
"""


def init_db() -> None:
    """建表(幂等)。server 启动时调用。"""
    with conn() as c:
        c.execute(_SCHEMA)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_dict(row: Any) -> Optional[dict]:
    return dict(row) if row is not None else None


def _j(value: Any) -> Any:
    return json.dumps(value, ensure_ascii=False) if value is not None else None


# ==================== documents ====================


def upsert_document(doc: dict) -> None:
    with conn() as c:
        c.execute(
            """
            INSERT INTO documents (id, name, ext, size, sha256, status, error, chunk_count, minio_key, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
              name=EXCLUDED.name, ext=EXCLUDED.ext, size=EXCLUDED.size, sha256=EXCLUDED.sha256,
              status=EXCLUDED.status, error=EXCLUDED.error, chunk_count=EXCLUDED.chunk_count,
              minio_key=EXCLUDED.minio_key, updated_at=EXCLUDED.updated_at
            """,
            (
                doc["id"], doc.get("name", ""), doc.get("ext", ""), int(doc.get("size", 0)),
                doc.get("sha256", ""), doc.get("status", "pending"), doc.get("error"),
                int(doc.get("chunk_count", 0)), doc.get("minio_key", ""), _now(), _now(),
            ),
        )


def get_document(doc_id: str) -> Optional[dict]:
    with conn() as c:
        return _row_dict(c.execute("SELECT * FROM documents WHERE id=%s", (doc_id,)).fetchone())


def get_document_by_name(name: str) -> Optional[dict]:
    with conn() as c:
        return _row_dict(
            c.execute("SELECT * FROM documents WHERE name=%s ORDER BY created_at DESC LIMIT 1", (name,)).fetchone()
        )


def get_documents_by_name(name: str) -> List[dict]:
    """取全部同名文档(按创建时间倒序)。同名替换时需清理所有历史记录,避免残留旧版。"""
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM documents WHERE name=%s ORDER BY created_at DESC", (name,)
        ).fetchall()
    return [_row_dict(r) for r in rows]


def list_documents() -> List[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
    return [_row_dict(r) for r in rows]


def set_document_status(doc_id: str, status: str, error: Optional[str] = None, chunk_count: Optional[int] = None) -> None:
    if chunk_count is not None:
        sql = "UPDATE documents SET status=%s, error=%s, chunk_count=%s, updated_at=%s WHERE id=%s"
        params = (status, error, chunk_count, _now(), doc_id)
    else:
        sql = "UPDATE documents SET status=%s, error=%s, updated_at=%s WHERE id=%s"
        params = (status, error, _now(), doc_id)
    with conn() as c:
        c.execute(sql, params)


def delete_document(doc_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM chunks WHERE doc_id=%s", (doc_id,))
        c.execute("DELETE FROM documents WHERE id=%s", (doc_id,))


def count_documents() -> int:
    with conn() as c:
        return int(c.execute("SELECT COUNT(*) FROM documents").fetchone()["count"])


# ==================== chunks ====================


def insert_chunks(chunks: List[dict]) -> None:
    if not chunks:
        return
    rows = [
        (
            ch.get("id") or uuid.uuid4().hex, ch["doc_id"], ch.get("doc_name", ""),
            int(ch.get("chunk_index", 0)), int(ch.get("char_start", 0)), int(ch.get("char_end", 0)),
            ch.get("text", ""),
        )
        for ch in chunks
    ]
    with conn() as c, c.cursor() as cur:
        cur.executemany(
            "INSERT INTO chunks (id, doc_id, doc_name, chunk_index, char_start, char_end, text) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            rows,
        )


def get_chunks(doc_id: str) -> List[dict]:
    with conn() as c:
        rows = c.execute("SELECT * FROM chunks WHERE doc_id=%s ORDER BY chunk_index", (doc_id,)).fetchall()
    return [_row_dict(r) for r in rows]


def get_chunk(doc_id: str, chunk_index: int) -> Optional[dict]:
    with conn() as c:
        return _row_dict(
            c.execute("SELECT * FROM chunks WHERE doc_id=%s AND chunk_index=%s", (doc_id, chunk_index)).fetchone()
        )


def delete_chunks(doc_id: str) -> None:
    with conn() as c:
        c.execute("DELETE FROM chunks WHERE doc_id=%s", (doc_id,))


# ==================== chat_logs ====================


def insert_chat_log(log: dict) -> int:
    with conn() as c:
        row = c.execute(
            """
            INSERT INTO chat_logs (session_id, user_id, platform, question, answer, tools_used, citations, tokens, refused)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """,
            (
                log.get("session_id", ""), log.get("user_id", ""), log.get("platform", ""),
                log.get("question", ""), log.get("answer", ""),
                _j(log.get("tools_used")), _j(log.get("citations")), _j(log.get("tokens")),
                bool(log.get("refused", False)),
            ),
        ).fetchone()
    return int(row["id"])


def query_chat_logs(
    user_id: Optional[str] = None,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> List[dict]:
    sql = "SELECT * FROM chat_logs WHERE 1=1"
    params: List[Any] = []
    if user_id:
        sql += " AND user_id=%s"
        params.append(user_id)
    if keyword:
        sql += " AND (question ILIKE %s OR answer ILIKE %s)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params += [limit, offset]
    with conn() as c:
        rows = c.execute(sql, params).fetchall()
    return [_row_dict(r) for r in rows]


# ==================== settings KV ====================


def set_setting(key: str, value: str) -> None:
    with conn() as c:
        c.execute(
            "INSERT INTO settings (key, value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            (key, value),
        )


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=%s", (key,)).fetchone()
    return row["value"] if row else default
