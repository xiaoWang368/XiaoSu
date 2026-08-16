from langchain_core.messages import HumanMessage

from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.llm_utils import get_llm_client

ROUTE_PROMPT = (
    "判断下面的用户问题应该走哪条路径,只回复一个词(knowledge / tool / refuse / chat),不要解释。\n"
    "knowledge = 需查公司文档/制度/知识库(年假/报销/入职等);\n"
    "tool = 需查员工/考勤/订单/时间等系统数据;\n"
    "refuse = 与公司无关或涉及敏感/未收录内容;\n"
    "chat = 问候/闲聊/询问小苏能做什么(如你好、你能帮我什么、你是谁、有哪些功能)。\n"
    "用户问题:{query}"
)

REWRITE_PROMPT = (
    "你是一个对话理解助手。请把用户的最新问题改写成:脱离上下文也能独立理解的一句话。\n"
    "规则:\n"
    "- 结合对话历史,补全指代(他/她/它/那个/上周/这家公司等)与省略的内容;\n"
    "- 只输出改写后的问题,不要解释、不要加前缀;\n"
    "- 如果最新问题本身已经完整清晰,直接原样输出。\n\n"
    "对话历史:\n{history}\n\n用户最新问题:{query}"
)


def _rewrite_query(state: QueryGraphState) -> str:
    """结合 history 把追问改写为独立问题;无历史或改写失败则退回原问题。"""
    query = state.get("original_query", "")
    history = state.get("history") or []
    if not history:
        return query
    try:
        llm = get_llm_client()
        history_text = "\n".join(
            f"{h.get('role', 'user')}: {h.get('content', '')}" for h in history[-6:]
        )
        resp = llm.invoke(
            [HumanMessage(content=REWRITE_PROMPT.format(history=history_text, query=query))]
        )
        rewritten = (resp.content or "").strip()
        if rewritten:
            logger.info(f"改写问题: {query} -> {rewritten}")
            return rewritten
    except Exception as e:  # noqa: BLE001
        logger.warning(f"问题改写失败,用原问题: {e}")
    return query


class NodeRoute(NodeBase):
    """
    意图路由:先结合 history 改写追问为独立问题,再 LLM 判断走 knowledge / tool / refuse。
    改写结果写入 rewritten_query,供检索节点使用(多轮对话的关键)。
    用文本判断(thinking 模式的模型不支持 tool_choice 强制调用)。
    """

    name: str = "node_route"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")
        query_text = _rewrite_query(state)
        intent = "knowledge"
        try:
            llm = get_llm_client()
            resp = llm.invoke([HumanMessage(content=ROUTE_PROMPT.format(query=query_text))])
            text = (resp.content or "").strip().lower()
            if "refuse" in text:
                intent = "refuse"
            elif "chat" in text or "greeting" in text:
                intent = "chat"
            elif "tool" in text:
                intent = "tool"
            else:
                intent = "knowledge"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"路由失败,默认 knowledge: {e}")
        logger.info(f"路由结果: {intent}")
        return {"intent": intent, "rewritten_query": query_text}
