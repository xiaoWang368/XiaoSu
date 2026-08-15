from __future__ import annotations

import logging
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from config.chroma_config import chroma_config

logger = logging.getLogger(__name__)

_chroma_client: Optional[chromadb.PersistentClient] = None
_collection_cache: dict = {}

def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client

    _chroma_client = chromadb.PersistentClient(
        path=chroma_config.persist_directory,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    logger.info(f"ChromaDB 客户端已初始化，持久化路径: {chroma_config.persist_directory}")
    return _chroma_client

def get_or_create_collection(
    name: str | None = None,
    embedding_function=None,
) -> chromadb.Collection:
    collection_name = name or chroma_config.collection_name
    if collection_name in _collection_cache:
        return _collection_cache[collection_name]

    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function,
    )
    _collection_cache[collection_name] = collection
    logger.info(f"ChromaDB 集合已就绪: {collection_name}")
    return collection

def list_collections() -> List[str]:
    return get_chroma_client().list_collections()

def delete_collection(name: str) -> None:
    client = get_chroma_client()
    try:
        client.delete_collection(name)
        _collection_cache.pop(name, None)
        logger.info(f"ChromaDB 集合已删除: {name}")
    except Exception:
        logger.warning(f"ChromaDB 集合不存在或删除失败: {name}")

def add_documents(
    ids: List[str],
    documents: List[str],
    metadatas: List[dict] | None = None,
    embeddings: List[List[float]] | None = None,
    collection_name: str | None = None,
) -> None:
    collection = get_or_create_collection(collection_name)
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )

def query(
    query_texts: List[str] | None = None,
    query_embeddings: List[List[float]] | None = None,
    n_results: int = 10,
    where: dict | None = None,
    collection_name: str | None = None,
) -> dict:
    collection = get_or_create_collection(collection_name)
    return collection.query(
        query_texts=query_texts,
        query_embeddings=query_embeddings,
        n_results=n_results,
        where=where,
    )

def delete_by_filter(
    where: dict,
    collection_name: str | None = None,
) -> None:
    collection = get_or_create_collection(collection_name)
    collection.delete(where=where)

if __name__ == "__main__":
    client = get_chroma_client()
    print(f"ChromaDB 心跳: {client.heartbeat()}")
    print(f"已有集合: {list_collections()}")