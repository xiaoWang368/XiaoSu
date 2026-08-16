from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from processor.query_processor.base import NodeBase
from processor.query_processor.prompt.answer import (
    ANSWER_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    REFUSAL_TEXT,
)
from processor.query_processor.state import QueryGraphState
from tool.logger import logger

# 检索相关度阈值:最高分低于此值 → 硬拒答(不调 LLM,防瞎编)。
# 确定性嵌入的 score=1-L2 范围:相关 ~ -0.2~-0.3,无关 < -0.87,取 -0.6 分隔。
MIN_RELEVANCE_SCORE = -0.6

# 问候/闲聊的友好介绍(不拒答)
GREETING_RESPONSE = (
    "你好!我是小苏,公司内部 AI 助手。\n\n"
    "我可以帮你:\n"
    "1. 查公司文档/制度:年假、报销、入职、考勤等(回答会附上文档出处);\n"
    "2. 查公司系统数据:员工信息、考勤、订单、当前时间;\n"
    "3. 多轮追问:比如接着问「他上周来上班几天」。\n\n"
    "试试问我「员工每年有几天年假?」或「员工 001 是哪个部门的?」"
)

_GREETING_WORDS = ("你好", "您好", "hello", "hi", "嗨", "在吗", "哈喽")
_CAPABILITY_WORDS = ("能做什么", "帮你做什么", "会做什么", "有哪些功能", "介绍一下", "你是谁", "自我介绍")
_TOPIC_WORDS = (
    "年假", "报销", "入职", "考勤", "员工", "订单", "请假", "加班", "出差",
    "工资", "社保", "福利", "发票", "假期", "几点", "时间", "部门", "离职",
)


def _is_greeting(query: str) -> bool:
    """判断是否为纯问候/能力询问(短句且不含具体主题词,避免误伤真实问题)。"""
    q = (query or "").lower().strip()
    if not q or len(q) > 20:
        return False
    if any(w in q for w in _TOPIC_WORDS):
        return False
    return any(w in q for w in _GREETING_WORDS) or any(w in q for w in _CAPABILITY_WORDS)


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

        intent = state.get("intent", "knowledge")

        # 闲聊/问候:不检索文档,交给 LLM 结合上下文回答(不拒答、不用固定文案)
        if intent == "chat" or _is_greeting(state.get("original_query", "")):
            state["refused"] = False
            messages = self._build_chat_messages(state)
            try:
                answer, usage = self._stream_answer(messages)
            except Exception as e:  # noqa: BLE001
                logger.error(f"闲聊 LLM 失败,回退固定介绍: {e}")
                state["answer"] = GREETING_RESPONSE
                return state
            state["answer"] = answer
            state["prompt_tokens"] = int(usage.get("prompt_tokens", 0))
            state["completion_tokens"] = int(usage.get("completion_tokens", 0))
            state["total_tokens"] = int(usage.get("total_tokens", 0))
            return state

        # 硬拒答:无关/敏感,或检索空/低分 → 不调 LLM
        sources = state.get("reranked_docs") or []
        top_score = max((s.get("score", 0) for s in sources), default=0.0)
        if intent == "refuse" or not sources or top_score < MIN_RELEVANCE_SCORE:
            state["answer"] = REFUSAL_TEXT
            state["refused"] = True
            return state

        # 知识库 RAG
        messages = self._build_messages(state, sources)
        try:
            answer, usage = self._stream_answer(messages)
        except Exception as e:  # noqa: BLE001
            logger.error(f"LLM 生成失败: {e}")
            raise
        state["answer"] = answer
        state["prompt_tokens"] = int(usage.get("prompt_tokens", 0))
        state["completion_tokens"] = int(usage.get("completion_tokens", 0))
        state["total_tokens"] = int(usage.get("total_tokens", 0))
        return state

    def _build_chat_messages(self, state):
        """闲聊消息:系统闲聊提示 + 最近上下文 + 当前问题(结合上下文回答)。"""
        messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)]
        for h in (state.get("history") or [])[-6:]:
            role, content = h.get("role"), h.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=state.get("original_query", "")))
        return messages

    def _stream_answer(self, messages):
        """OpenAI 客户端流式生成,采集 token 用量(stream_options.include_usage)。"""
        from openai import OpenAI
        from config.llm_config import llm_config

        client = OpenAI(api_key=llm_config.api_key, base_url=llm_config.base_url)
        role_map = {"system": "system", "human": "user", "ai": "assistant"}
        payload = [{"role": role_map.get(m.type, "user"), "content": m.content or ""} for m in messages]

        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        answer_parts: list[str] = []
        stream = client.chat.completions.create(
            model=llm_config.llm_model,
            messages=payload,
            temperature=llm_config.temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                answer_parts.append(text)
                if self.on_token:
                    self.on_token(text)
            if chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens or 0,
                    "completion_tokens": chunk.usage.completion_tokens or 0,
                    "total_tokens": chunk.usage.total_tokens or 0,
                }
        return "".join(answer_parts), usage

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
