from processor.query_processor.base import NodeBase
from processor.retrieval import retrieve
from processor.query_processor.state import QueryGraphState
from tool.logger import logger


class NodeSearchEmbeddingHyde(NodeBase):
    """
    节点功能:HyDE (Hypothetical Document Embedding)。
    先让 LLM 生成假设性答案,再用它向量检索,提高召回。LLM 不可用时返回空,不影响主流程。
    """

    name: str = "node_search_embedding_hyde"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")
        query_text = state.get("rewritten_query") or state.get("original_query", "")
        hypo = self._hypothetical_answer(query_text)
        if not hypo:
            return {"hyde_embedding_chunks": []}
        chunks = retrieve(hypo)
        logger.info(f"HyDE 检索到 {len(chunks)} 条")
        return {"hyde_embedding_chunks": chunks}

    def _hypothetical_answer(self, query_text: str) -> str:
        if not query_text:
            return ""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from utils.llm_utils import get_llm_client
            llm = get_llm_client()
            resp = llm.invoke([
                SystemMessage(content="请针对问题写一段简洁的假设性回答(语气客观,像公司文档),不要解释,直接写内容。"),
                HumanMessage(content=query_text),
            ])
            return (resp.content or "").strip()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"HyDE 生成失败,跳过: {e}")
            return ""
