"""
确定性本地嵌入器(离线兜底,无依赖、可复现)。

用途:当 utils.embedding_utils(BGE-M3,需要本地模型)不可用时,为导入/检索提供稳定向量,
保证演示在无模型、无 GPU、无网络的机器上也能跑。维度与 BGE-M3 dense(1024)一致。

算法:字符一元 + 二元 gram 计数 → 稳定哈希桶 → L2 归一化。对关键词重叠的中文问答(员工手册)够用。
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path


def _stable_idx(gram: str, dim: int) -> int:
    """稳定哈希(不受进程盐影响),把 gram 映射到 [0, dim)。"""
    return int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16) % dim


DASHSCOPE_EMBEDDING_MODEL = "text-embedding-v3"
DASHSCOPE_EMBEDDING_DIM = 1024


def embed_dense(texts: list[str]) -> list[list[float]]:
    """
    与导入一致的稠密嵌入,维度固定 1024。
    一律使用确定性嵌入(无状态、任何进程结果一致),从根上保证导入/查询同一向量空间,
    杜绝 DashScope 时好时坏导致的"检索到 0 条"。
    """
    return deterministic_embeddings(texts)


def _embed_dashscope(texts: list[str]) -> list[list[float]]:
    """DashScope text-embedding-v3(OpenAI 兼容)。失败抛错(不静默降级,避免向量空间错乱)。"""
    from openai import OpenAI
    from processor.settings import get_settings
    s = get_settings()
    client = OpenAI(api_key=s.openai_api_key, base_url=s.openai_api_base)
    resp = client.embeddings.create(
        model=DASHSCOPE_EMBEDDING_MODEL,
        input=texts,
        dimensions=DASHSCOPE_EMBEDDING_DIM,
        encoding_format="float",
    )
    return [d.embedding for d in resp.data]


# 中文常见停用词(降权处理)
_STOPWORDS = {
    "的", "了", "吗", "呢", "啊", "和", "与", "及", "或", "是", "在", "有", "为", "对", "等",
    "一个", "什么", "怎么", "多少", "这", "那", "我", "你", "他", "她", "它", "要", "能", "会", "把", "被",
}


def deterministic_embeddings(texts: list[str], dim: int = 1024) -> list[list[float]]:
    """
    确定性嵌入(离线兜底):jieba 词级 + 字符 bigram 哈希计数 → L2 归一化。
    词级使中文关键词(年假/报销/入职)区分度更高。
    """
    import jieba
    results: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        s = text.strip()
        for word in jieba.lcut(s):
            w = word.strip()
            if not w or w in _STOPWORDS:
                continue
            vec[_stable_idx(w, dim)] += 2.0  # 词权重更高
            for i in range(len(w) - 1):
                vec[_stable_idx(w[i:i + 2], dim)] += 1.0
        for i in range(len(s) - 1):
            vec[_stable_idx(s[i:i + 2], dim)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        results.append(vec)
    return results
