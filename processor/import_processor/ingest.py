"""
导入门面:上传 → sha256 去重 / 同名替换 → 原文件存 MinIO → 跑 LangGraph 导入图 → 状态机。

供 Web 上传接口(后台)与启动自动灌库调用。
"""

from __future__ import annotations

import hashlib
import io
import logging
import shutil
from pathlib import Path

from config.minio_config import minio_config
from processor.db import (
    count_documents,
    delete_document,
    get_documents_by_name,
    init_db,
    list_documents as db_list_documents,
    set_document_status,
    upsert_document,
)
from processor.import_processor.io_paths import doc_dir, new_doc_id
from processor.import_processor.main_graph import KBImportWorkflow
from utils.chroma_utils import delete_by_filter
from utils.minio_utils import get_minio_client

logger = logging.getLogger("ingest")

SEED_DIR = Path("data/seed")
SUPPORTED_EXTS = {".md", ".txt", ".pdf", ".docx"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _purge_document(existing: dict) -> None:
    """彻底清理一条文档记录:向量、PG 元数据、MinIO 原始文件、本地备份目录。"""
    doc_id = existing["id"]
    try:
        delete_by_filter({"doc_id": doc_id})
    except Exception:  # noqa: BLE001
        logger.warning(f"清理旧向量失败(可忽略): {doc_id}")
    delete_document(doc_id)
    try:
        minio_key = existing.get("minio_key") or f"{doc_id}/{existing.get('name', '')}"
        if minio_key:
            get_minio_client().remove_object(minio_config.bucket_name, minio_key)
    except Exception:  # noqa: BLE001
        logger.warning(f"清理 MinIO 对象失败(可忽略): {minio_key}")
    try:
        local_dir = doc_dir(doc_id)
        if local_dir.exists():
            shutil.rmtree(local_dir)
    except Exception:  # noqa: BLE001
        logger.warning(f"清理本地备份失败(可忽略): {doc_id}")
    logger.info(f"同名不同内容,替换旧文档: {doc_id}")


def import_document(filename: str, content: bytes, doc_id: str | None = None) -> dict:
    """
    导入一个文档(同步,适合后台线程 / 启动灌库调用)。

    返回:{"doc_id", "changed", "chunk_count"}。
    状态机:upload → pending → indexing → indexed | failed。
    """
    name = filename
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(f"不支持的文件格式: {ext}")

    init_db()  # 确保 PG 表存在(幂等)

    digest = _sha256(content)

    # 增量去重:同名 + 同内容 + 已 indexed → 跳过,不重复处理
    existing_list = get_documents_by_name(name)
    for existing in existing_list:
        if existing["sha256"] == digest and existing["status"] == "indexed":
            logger.info(f"同名同内容,跳过: {name}")
            return {"doc_id": existing["id"], "changed": False, "chunk_count": existing.get("chunk_count", 0)}

    # 同名不同内容 → 替换:清理所有同名历史记录(PG + Chroma + MinIO + 本地备份),避免旧版残留
    for existing in existing_list:
        _purge_document(existing)

    doc_id = doc_id or new_doc_id()
    minio_key = f"{doc_id}/{name}"

    # 原文件 → MinIO(公开读,供 pdf.js 等直接访问)
    client = get_minio_client()
    client.put_object(minio_config.bucket_name, minio_key, io.BytesIO(content), len(content))

    # 本地备份到项目外的其他磁盘目录 {LOCAL_UPLOAD_DIR}/{doc_id}/(供图解析)
    local_dir = doc_dir(doc_id)
    local_path = local_dir / name
    local_path.write_bytes(content)

    upsert_document({
        "id": doc_id, "name": name, "ext": ext, "size": len(content),
        "sha256": digest, "status": "pending", "chunk_count": 0, "minio_key": minio_key,
    })

    # 跑导入图
    set_document_status(doc_id, "indexing")
    try:
        state = {
            "import_file_path": str(local_path),
            "file_dir": str(local_dir),
            "doc_id": doc_id,
            "doc_name": name,
            "file_title": Path(name).stem,
        }
        result = KBImportWorkflow().run(state, stream=False)
        chunks = result.get("chunks") or []
        set_document_status(doc_id, "indexed", chunk_count=len(chunks))
        logger.info(f"导入完成: {name} ({doc_id}), chunks={len(chunks)}")
        return {"doc_id": doc_id, "changed": True, "chunk_count": len(chunks)}
    except Exception as exc:  # noqa: BLE001
        set_document_status(doc_id, "failed", error=str(exc))
        logger.exception(f"导入失败: {name} ({doc_id})")
        raise


def seed_from_directory(dir_path: str | Path = SEED_DIR) -> dict:
    """启动自动灌库:文档库为空时,把 data/seed/ 下的种子文档灌入(面试官零操作即可用)。"""
    if count_documents() > 0:
        return {"seeded": False, "reason": "already_has_docs"}
    d = Path(dir_path)
    if not d.is_dir():
        return {"seeded": False, "reason": "no_seed_dir"}
    results = []
    for f in sorted(d.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            try:
                results.append({"file": f.name, **import_document(f.name, f.read_bytes())})
            except Exception as exc:  # noqa: BLE001
                results.append({"file": f.name, "error": str(exc)})
    return {"seeded": True, "results": results}


def list_documents() -> list[dict]:
    """后台「文档管理」列表(含索引状态 pending/indexing/indexed/failed)。"""
    return db_list_documents()
