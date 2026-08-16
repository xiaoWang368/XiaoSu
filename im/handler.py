"""统一消息处理(平台无关):会话 → 调 query_processor 门面 → 格式化引用 → 回发。

各渠道(channels/*)只做协议收发,把 (platform, user_id, conversation_id, text) 交给这里;
多轮上下文、查询、引用格式化、错误兜底都在本层,保证多端复用。
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import List

from im.session import SessionStore
from processor.query_processor.service import QueryService

logger = logging.getLogger("im.handler")

QUERY_TIMEOUT_S = 60
FALLBACK_TEXT = "小苏开小差了,请稍后再试 🙏"
# 引用链接的后端地址(演示用本机;部署时改成公网可达地址)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def format_reply(answer: str, citations: List) -> str:
    """答案 + 引用 → markdown(引用用可点击链接,IM 里清晰呈现)。"""
    if not citations:
        return answer
    lines = [answer, "", "---", "**参考来源**:"]
    for c in citations:
        url = f"{BACKEND_URL}{c.url}"  # c.url = /doc/{doc_id}?chunk={n}
        lines.append(f"[【{c.ref}】{c.doc_name}]({url})")
    return "\n".join(lines)


class MessageHandler:
    """平台无关统一处理。"""

    def __init__(self, query_service: QueryService | None = None):
        self.sessions = SessionStore()
        self.query = query_service or QueryService()

    async def handle(self, platform: str, user_id: str, conversation_id: str, text: str) -> str:
        """处理一条消息,返回要回发的 markdown 文本。失败/超时返回兜底文案。"""
        try:
            history = self.sessions.get_history(platform, user_id, conversation_id)
            result = await asyncio.wait_for(
                self.query.query(
                    session_id=f"{platform}:{user_id}:{conversation_id}",
                    message=text,
                    history=history,
                    user_id=user_id,
                    platform=platform,
                ),
                timeout=QUERY_TIMEOUT_S,
            )
            self.sessions.append(platform, user_id, conversation_id, text, result.answer)
            return format_reply(result.answer, result.citations)
        except asyncio.TimeoutError:
            logger.warning(f"IM 查询超时({QUERY_TIMEOUT_S}s): {platform}:{user_id}")
            return FALLBACK_TEXT
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"IM 处理失败: {exc}")
            return FALLBACK_TEXT
