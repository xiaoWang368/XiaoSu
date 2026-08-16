from processor.query_processor.base import NodeBase
from processor.retrieval import retrieve
from processor.query_processor.state import QueryGraphState
from tool.logger import logger


class NodeSearchEmbedding(NodeBase):
    """
    节点功能:基于用户问题做向量检索(Chroma),返回带定位元数据的切片。
    """

    name: str = "node_search_embedding"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")
        query_text = state.get("rewritten_query") or state.get("original_query", "")
        chunks = retrieve(query_text)
        logger.info(f"检索到 {len(chunks)} 条")
        return {"embedding_chunks": chunks}
