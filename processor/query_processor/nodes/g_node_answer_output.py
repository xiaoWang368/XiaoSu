from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from processor.query_processor.base import NodeBase
from processor.query_processor.prompt.answer import ANSWER_SYSTEM_PROMPT, REFUSAL_TEXT
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.llm_utils import get_llm_client

# 检索相关度阈值:最高分低于此值 → 硬拒答(不调 LLM,防瞎编)。
# 确定性嵌入的 score=1-L2 范围:相关 ~ -0.2~-0.3,无关 < -0.87,取 -0.6 分隔。
MIN_RELEVANCE_SCORE = -0.6


class NodeAnswerOutput(NodeBase):
    """
    节点功能:答案生成。引用【N】+ 硬拒答 + 流式(on_token 回调)。
    """

    name: str = "node_answer_output"

    def __init__(self, on_token=None):
        super().__init__()
        self.on_token = on_token

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")

        # 已有答案(工具路径产生)→ 透传
        if state.get("answer"):
            return state

        # 硬拒答:无检索来源 或 最高分过低 → 不调 LLM
        sources = state.get("reranked_docs") or []
        top_score = max((s.get("score", 0) for s in sources), default=0.0)
        if not sources or top_score < MIN_RELEVANCE_SCORE:
            state["answer"] = REFUSAL_TEXT
            state["refused"] = True
            return state

        messages = self._build_messages(state, sources)
        llm = get_llm_client()
        answer_parts: list[str] = []
        try:
            for chunk in llm.stream(messages):
                text = getattr(chunk, "content", "") or ""
                if text:
                    answer_parts.append(text)
                    if self.on_token:
                        self.on_token(text)
                usage = (getattr(chunk, "response_metadata", {}) or {}).get("token_usage") or {}
                if usage.get("total_tokens"):
                    state["prompt_tokens"] = int(usage.get("prompt_tokens", 0))
                    state["completion_tokens"] = int(usage.get("completion_tokens", 0))
                    state["total_tokens"] = int(usage.get("total_tokens", 0))
        except Exception as e:  # noqa: BLE001
            logger.error(f"LLM 生成失败: {e}")
            raise
        state["answer"] = "".join(answer_parts)
        return state

    def _build_messages(self, state, sources):
        system = ANSWER_SYSTEM_PROMPT.format(today=date.today().isoformat())
        messages = [SystemMessage(content=system)]
        for h in state.get("history") or []:
            role, content = h.get("role"), h.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        ctx = "\n".join(
            f"【{i}】来自《{s.get('doc_name', '')}》: {str(s.get('content', ''))[:800]}"
            for i, s in enumerate(sources, start=1)
        )
        user = f"用户问题:{state.get('original_query', '')}\n\n检索到的资料:\n{ctx}"
        messages.append(HumanMessage(content=user))
        return messages
