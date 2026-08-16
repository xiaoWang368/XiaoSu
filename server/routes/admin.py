"""
管理后台 API:文档上传 / 列表 / 详情 / 文本 / 删除。
尽量复用现有模块:
  - processor.import_processor.ingest: import_document / list_documents
  - processor.db: upsert/get/list/delete document、get_chunks
  - utils.chroma_utils: delete_by_filter(删向量)
  - utils.minio_utils + config.minio_config: 删 MinIO 原文件
  - processor.import_processor.io_paths: new_doc_id / doc_dir(本地备份)
"""



from __future__ import annotations

import asyncio
import hashlib
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from config.minio_config import minio_config
from processor.db import (
    delete_document,
    get_chunks,
    get_document,
    get_documents_by_name,
    list_documents as db_list_documents,
    query_chat_logs,
    upsert_document,
)
from processor.import_processor.ingest import import_document
from processor.import_processor.io_paths import doc_dir, new_doc_id
from utils.chroma_utils import delete_by_filter
from utils.minio_utils import get_minio_client

logger = logging.getLogger("server.admin")
router = APIRouter()

SUPPORTED_EXTS = {".md", ".txt", ".pdf", ".docx"}


async def _run_import(name: str, content: bytes, doc_id: str) -> None:
    """后台跑导入(异步)。异常仅记日志,状态已由 ingest 标记 failed。"""
    try:
        result = await asyncio.to_thread(import_document, name, content, doc_id)
        if result.get("doc_id") != doc_id:
            # 去重跳过了(返回已有文档)→ 清理本次预建的 pending 幽灵行,避免列表出现永久 pending
            delete_document(doc_id)
            try:
                delete_by_filter({"doc_id": doc_id})
            except Exception:  # noqa: BLE001
                pass
            logger.info(f"重复上传已复用已有文档,清理预建 pending: {doc_id}")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"后台导入失败: {name} ({doc_id}): {exc}")


@router.post("/docs")
async def upload_doc(file: UploadFile = File(...)):
    """上传文档:校验格式 → 预建 pending 行 → 后台导入 → 立即返回 doc_id。"""
    name = file.filename or ""
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")
    content = await file.read()

    # 同名同内容已 indexed → 直接复用已有文档,不重复导入(避免产生卡死的 pending 幽灵)
    digest = hashlib.sha256(content).hexdigest()
    for ex in get_documents_by_name(name):
        if ex["sha256"] == digest and ex["status"] == "indexed":
            return {"doc_id": ex["id"], "name": name, "status": ex["status"], "duplicate": True}

    doc_id = new_doc_id()
    upsert_document({
        "id": doc_id, "name": name, "ext": ext, "size": len(content),
        "sha256": "", "status": "pending", "chunk_count": 0, "minio_key": f"{doc_id}/{name}",
    })
    asyncio.create_task(_run_import(name, content, doc_id))
    return {"doc_id": doc_id, "name": name, "status": "pending"}


@router.get("/docs")
async def docs_list():
    """文档列表(含索引状态)。"""
    return await asyncio.to_thread(db_list_documents)


@router.get("/logs")
async def logs(
    user_id: str | None = None,
    keyword: str | None = None,
    page: int = 0,
    limit: int = 50,
):
    """对话日志:提问/回答/工具调用/Token 消耗/是否拒答,供管理后台展示。"""
    return await asyncio.to_thread(
        query_chat_logs, user_id=user_id, keyword=keyword, offset=page * limit, limit=limit
    )


@router.get("/settings")
async def settings():
    """当前配置:模型 / 嵌入 / IM 平台与接入状态(设置页展示)。"""
    import os
    from config.llm_config import llm_config
    try:
        from processor.embed import DASHSCOPE_EMBEDDING_MODEL, DASHSCOPE_EMBEDDING_DIM
    except Exception:  # noqa: BLE001
        DASHSCOPE_EMBEDDING_MODEL, DASHSCOPE_EMBEDDING_DIM = "text-embedding-v3", 1024
    return {
        "model": llm_config.llm_model,
        "temperature": llm_config.temperature,
        "embedding_model": DASHSCOPE_EMBEDDING_MODEL,
        "embedding_dim": DASHSCOPE_EMBEDDING_DIM,
        "im_platform": "dingtalk",
        "dingtalk_configured": bool(os.getenv("DINGTALK_APP_KEY") and os.getenv("DINGTALK_APP_SECRET")),
    }


@router.get("/settings/im-status")
async def im_status():
    import os
    return {
        "platform": "dingtalk",
        "configured": bool(os.getenv("DINGTALK_APP_KEY") and os.getenv("DINGTALK_APP_SECRET")),
        "connected": False,  # 钉钉 worker 进程启动后由它更新
    }


@router.get("/docs/{doc_id}")
async def doc_detail(doc_id: str):
    doc = await asyncio.to_thread(get_document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.get("/docs/{doc_id}/text")
async def doc_text(doc_id: str):
    """该文档抽取文本(拼接 chunks,供查看页高亮)。"""
    chunks = await asyncio.to_thread(get_chunks, doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="文档不存在或无内容")
    text = "\n\n".join(str(c.get("text", "")) for c in chunks)
    return {"doc_id": doc_id, "text": text}


@router.delete("/docs/{doc_id}")
async def doc_delete(doc_id: str):
    """删除文档:Chroma 向量 + PG 记录/chunks + MinIO 原文件 + 本地备份目录。"""
    def _do() -> dict:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        try:
            delete_by_filter({"doc_id": doc_id})
        except Exception:  # noqa: BLE001
            logger.warning(f"删除向量失败(可忽略): {doc_id}")
        delete_document(doc_id)  # 删 PG 记录 + chunks
        try:
            get_minio_client().remove_object(minio_config.bucket_name, f"{doc_id}/{doc['name']}")
        except Exception:  # noqa: BLE001
            logger.warning(f"删除 MinIO 对象失败(可忽略): {doc_id}")
        shutil.rmtree(doc_dir(doc_id), ignore_errors=True)
        logger.info(f"文档已删除: {doc_id}")
        return {"deleted": doc_id}
    return await asyncio.to_thread(_do)
