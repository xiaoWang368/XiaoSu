from langchain_core.messages import HumanMessage

from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.llm_utils import get_llm_client

ROUTE_PROMPT = (
    "判断下面的用户问题应该走哪条路径,只回复一个词(knowledge / tool / refuse),不要解释。\n"
    "knowledge = 需查公司文档/制度/知识库(年假/报销/入职等);\n"
    "tool = 需查员工/考勤/订单/时间等系统数据;\n"
    "refuse = 与公司无关或涉及敏感/未收录内容。\n"
    "用户问题:{query}"
)


class NodeRoute(NodeBase):
    """
    意图路由:LLM 自主判断走 knowledge / tool / refuse。
    用文本判断(thinking 模式的模型不支持 tool_choice 强制调用)。
    """

    name: str = "node_route"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")
        query_text = state.get("original_query", "")
        intent = "knowledge"
        try:
            llm = get_llm_client()
            resp = llm.invoke([HumanMessage(content=ROUTE_PROMPT.format(query=query_text))])
            text = (resp.content or "").strip().lower()
            if "refuse" in text:
                intent = "refuse"
            elif "tool" in text:
                intent = "tool"
            else:
                intent = "knowledge"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"路由失败,默认 knowledge: {e}")
        logger.info(f"路由结果: {intent}")
        return {"intent": intent}
