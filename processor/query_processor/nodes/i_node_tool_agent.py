import os
from datetime import datetime

import requests
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from processor.query_processor.base import NodeBase
from processor.query_processor.prompt.answer import TOOL_SYSTEM_PROMPT
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.llm_utils import get_llm_client

MAX_ITERS = 4
MOCK_API_BASE = os.getenv("MOCK_API_BASE", "http://127.0.0.1:8001")

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_employee",
            "description": "按工号查员工部门/职位/入职时间",
            "parameters": {
                "type": "object",
                "properties": {"emp_id": {"type": "string", "description": "员工工号,如 001"}},
                "required": ["emp_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attendance",
            "description": "查员工某时间段的考勤(工作日天数)",
            "parameters": {
                "type": "object",
                "properties": {
                    "emp_id": {"type": "string"},
                    "start": {"type": "string", "description": "YYYY-MM-DD"},
                    "end": {"type": "string", "description": "YYYY-MM-DD"},
                },
                "required": ["emp_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders",
            "description": "查某时间段的订单汇总(数量/总金额)",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "YYYY-MM-DD"},
                    "end": {"type": "string", "description": "YYYY-MM-DD"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前日期时间",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class NodeToolAgent(NodeBase):
    """
    工具调用循环:LLM 自主决定调用哪些工具(get_employee/get_attendance/get_orders/get_current_time),
    直到给出最终答案。
    """

    name: str = "node_tool_agent"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        logger.info(f"【{self.name}】节点逻辑")
        messages = [SystemMessage(content=TOOL_SYSTEM_PROMPT)]
        for h in state.get("history") or []:
            role, content = h.get("role"), h.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=state.get("original_query", "")))

        llm_tools = get_llm_client().bind_tools(TOOL_SCHEMAS)
        tools_used = list(state.get("tools_used") or [])
        answer = ""
        for _ in range(MAX_ITERS):
            resp = llm_tools.invoke(messages)
            tool_calls = resp.tool_calls or []
            if not tool_calls:
                answer = resp.content or ""
                break
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("args", {}) or {}
                logger.info(f"调用工具: {name}({args})")
                result = self._execute_tool(name, args)
                tools_used.append(name)
                messages.append(AIMessage(content="", tool_calls=[tc]))
                messages.append(ToolMessage(content=result, tool_call_id=tc.get("id", "")))
        state["tools_used"] = tools_used
        if answer:
            state["answer"] = answer
        return state

    def _execute_tool(self, name: str, args: dict) -> str:
        try:
            if name == "get_employee":
                r = requests.get(f"{MOCK_API_BASE}/api/employee/{args.get('emp_id', '')}", timeout=5)
                return r.text if r.status_code == 200 else "查无此人"
            if name == "get_attendance":
                params = {k: args[k] for k in ("emp_id", "start", "end") if args.get(k)}
                r = requests.get(f"{MOCK_API_BASE}/api/attendance", params=params, timeout=5)
                return r.text if r.status_code == 200 else "查询失败"
            if name == "get_orders":
                params = {k: args[k] for k in ("start", "end") if args.get(k)}
                r = requests.get(f"{MOCK_API_BASE}/api/orders", params=params, timeout=5)
                return r.text if r.status_code == 200 else "查询失败"
            if name == "get_current_time":
                return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:  # noqa: BLE001
            return f"工具调用失败:{e}"
        return "未知工具"
