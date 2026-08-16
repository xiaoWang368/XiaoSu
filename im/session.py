"""会话/多轮上下文管理:按 (platform, user_id, conversation_id) 隔离。

- 群聊里 A/B 的 sender_staff_id 不同 → 各自独立上下文,不会串。
- 同一会话多轮连续(支撑「他=001」这类指代)。
- 内存存储,每会话保留最近 MAX_HISTORY 轮;chat_logs 已落 PG 可回溯。
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Tuple


class SessionStore:
    MAX_HISTORY = 20

    def __init__(self) -> None:
        self._sessions: Dict[Tuple[str, str, str], Deque[Dict]] = {}

    @staticmethod
    def _key(platform: str, user_id: str, conversation_id: str) -> Tuple[str, str, str]:
        return (platform, user_id, conversation_id)

    def get_history(self, platform: str, user_id: str, conversation_id: str) -> List[Dict]:
        q = self._sessions.get(self._key(platform, user_id, conversation_id))
        return list(q) if q else []

    def append(self, platform: str, user_id: str, conversation_id: str, user_msg: str, assistant_msg: str) -> None:
        key = self._key(platform, user_id, conversation_id)
        q = self._sessions.setdefault(key, deque(maxlen=self.MAX_HISTORY))
        q.append({"role": "user", "content": user_msg})
        q.append({"role": "assistant", "content": assistant_msg})

    def clear(self, platform: str, user_id: str, conversation_id: str) -> None:
        self._sessions.pop(self._key(platform, user_id, conversation_id), None)
