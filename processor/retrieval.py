"""
检索共享逻辑:b_node(向量检索) / c_node(HyDE) 复用。
把 Chroma 查询结果转成带定位元数据的 chunk 列表(doc_id/doc_name/chunk_index/char_start/char_end)。
"""

from __future__ import annotations

from processor.embed import embed_dense
from utils.chroma_utils import query as chroma_query

TOP_K = 6


def _to_chunks(res: dict) -> list[dict]:
    chunks: list[dict] = []
    if not res or not res.get("ids"):
        return chunks
    ids0 = res["ids"][0] or []
    docs0 = res.get("documents", [[]])[0] or []
    metas0 = res.get("metadatas", [[]])[0] or []
    dists0 = res.get("distances", [[]])[0] or []
    for i, cid in enumerate(ids0):
        meta = metas0[i] if i < len(metas0) else {}
        chunks.append({
            "id": cid,
            "doc_id": meta.get("doc_id", ""),
            "doc_name": meta.get("doc_name", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "char_start": meta.get("char_start", 0),
            "char_end": meta.get("char_end", 0),
            "content": docs0[i] if i < len(docs0) else "",
            "score": (1.0 - dists0[i]) if i < len(dists0) else 0.0,
        })
    return chunks


def retrieve(query_text: str, top_k: int = TOP_K) -> list[dict]:
    """嵌入查询 → Chroma 检索 → 返回带定位元数据的 chunks。"""
    if not query_text:
        return []
    vec = embed_dense([query_text])[0]
    res = chroma_query(query_embeddings=[vec], n_results=top_k)
    return _to_chunks(res)
