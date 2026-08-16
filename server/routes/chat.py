"""
POST /api/chat —— SSE 流式问答。

IM 与 Web 调试页复用同一个查询门面（processor.query_processor.service.QueryService），
把门面的 SSEEvent 流原样透出为 text/event-stream：
    event: status    data: {"message": "正在理解问题…"}
    event: status    data: {"node": "...", "message": "正在执行 node_xxx"}
    event: tool      data: {"name": "...", "args": "..."}          # 工具调用（LangGraph 支持后出现）
    event: citation  data: {"citations": [...]}
    event: delta     data: {"text": "..."}
    event: done      data: {"answer": "...", "citations": [...], "usage": {...}}
    event: error     data: {"message": "小苏暂时有点忙，请稍后再试"}

异常一律归一为 event: error 并返回 HTTP 200，绝不裸 500（笔试题 7.5 工程鲁棒性要求）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from processor.query_processor.service import QueryError, QueryService, SSEEvent

logger = logging.getLogger("server.chat")

router = APIRouter()

# 单例门面：IM / Web 共用
_svc = QueryService()


class ChatRequest(BaseModel):
    session_id: str = ""
    user_id: str = "web"
    platform: str = "web"
    message: str = Field(..., min_length=1, description="用户消息")
    history: List[Dict[str, str]] = Field(default_factory=list, description="多轮上下文 [{role, content}]")


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


_FRIENDLY_MESSAGES = {
    "auth": "模型配置似乎有问题（API Key 无效或未配置），请联系管理员。",
    "rate": "请求太频繁了，请稍后再试。",
    "network": "网络连接失败，请稍后再试。",
    "timeout": "小苏思考太久啦，请稍后再试。",
    "engine": "小苏暂时有点忙，请稍后再试。",
}


def _error_payload(exc: Exception) -> Dict[str, Any]:
    kind = exc.kind if isinstance(exc, QueryError) else "unknown"
    return {"message": _FRIENDLY_MESSAGES.get(kind, "小苏暂时有点忙，请稍后再试。"), "kind": kind}


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        yield _sse("status", {"message": "正在理解问题…"})
        try:
            async for ev in _svc.stream_query(
                req.session_id, req.message, req.history or [], req.user_id, req.platform
            ):
                yield _sse(ev.type, ev.data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("chat SSE 失败")
            yield _sse("error", _error_payload(exc))

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用代理缓冲，保证逐条下发
        },
    )
