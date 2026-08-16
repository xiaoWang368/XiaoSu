from processor.query_processor.base import NodeBase
from processor.retrieval import TOP_K
from processor.query_processor.state import QueryGraphState
from tool.logger import logger


class NodeRerank(NodeBase):
    """
    节点功能:对 RRF 结果取 Top-K(无本地 cross-encoder,先透传截断)。
    """

    name: str = "node_rerank"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")
        docs = state.get("rrf_chunks") or []
        state["reranked_docs"] = docs[:TOP_K]
        return state
