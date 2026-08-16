from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger


class NodeRrf(NodeBase):
    """
    节点功能:Reciprocal Rank Fusion。将多路召回(向量/HyDE/Web)按排名加权融合。
    """

    name: str = "node_rrf"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")
        sources = [
            state.get("embedding_chunks") or [],
            state.get("hyde_embedding_chunks") or [],
            state.get("web_search_docs") or [],
        ]
        merged: dict = {}  # (doc_id, chunk_index) -> [chunk, rrf_score]
        for lst in sources:
            for rank, ch in enumerate(lst):
                key = (ch.get("doc_id", ""), ch.get("chunk_index", 0))
                score = 1.0 / (60 + rank)
                if key in merged:
                    merged[key][1] += score
                else:
                    merged[key] = [ch, score]
        ranked = sorted(merged.values(), key=lambda x: x[1], reverse=True)
        state["rrf_chunks"] = [item[0] for item in ranked]
        return state
