import logging
from typing import Any, Dict, List

from processor.db import delete_chunks, init_db, insert_chunks
from processor.import_processor.base import BaseNode
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState
from utils.chroma_utils import add_documents, delete_by_filter


class NodeImportMilvus(BaseNode):
    """
    入库节点(历史命名保留):Chroma 向量 + PostgreSQL chunks 文本持久化。

    每个 chunk 写入:
      - PostgreSQL chunks 表:text + doc_id/doc_name/chunk_index/char_start/char_end(引用定位)
      - Chroma 集合:稠密向量 + 同样 metadata
    幂等:先清该 doc_id 的旧数据,再写。
    """

    name = "node_import_milvus"

    def process(self, state: ImportGraphState):
        logging.info(f"{self.name}节点开始执行")
        init_db()  # 确保 PG 表存在(幂等,直接跑图时也安全)
        chunks = self._step_1_validate(state)
        doc_id = state.get("doc_id") or chunks[0].get("doc_id")
        doc_name = state.get("doc_name") or chunks[0].get("doc_name") or ""
        if not doc_id:
            raise StateFieldError(field_name="doc_id", message="缺少 doc_id", expected_type=str)

        # 幂等:清该 doc_id 旧数据
        self._clear_old(doc_id)

        # 1. 文本元数据落 PG
        rows: List[Dict[str, Any]] = []
        for idx, ch in enumerate(chunks):
            rows.append({
                "id": f"{doc_id}:{ch.get('chunk_index', idx)}",
                "doc_id": doc_id,
                "doc_name": doc_name,
                "chunk_index": ch.get("chunk_index", idx),
                "char_start": ch.get("char_start", 0),
                "char_end": ch.get("char_end", 0),
                "text": ch.get("content", ""),
            })
        insert_chunks(rows)

        # 2. 稠密向量落 Chroma
        add_documents(
            ids=[r["id"] for r in rows],
            documents=[r["text"] for r in rows],
            metadatas=[
                {
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "chunk_index": r["chunk_index"],
                    "char_start": r["char_start"],
                    "char_end": r["char_end"],
                }
                for r in rows
            ],
            embeddings=[ch["dense_embedding"] for ch in chunks],
        )
        logging.info(f"{self.name} 入库完成: doc={doc_id}, chunks={len(rows)}")
        return state

    def _step_1_validate(self, state) -> List[Dict[str, Any]]:
        chunks = state.get("chunks")
        if not chunks:
            raise StateFieldError(field_name="chunks", message="chunks 不能为空", expected_type=list)
        if "dense_embedding" not in chunks[0]:
            raise StateFieldError(field_name="chunks", message="缺少 dense_embedding 字段")
        return chunks

    def _clear_old(self, doc_id: str) -> None:
        try:
            delete_by_filter({"doc_id": doc_id})
        except Exception:  # noqa: BLE001
            logging.warning(f"{self.name} 清理 Chroma 旧数据失败(可忽略): {doc_id}")
        delete_chunks(doc_id)
