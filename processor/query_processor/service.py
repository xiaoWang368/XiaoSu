"""
查询门面(service layer)

IM 与 Web 两条入口共用的唯一对外接口：内部驱动 LangGraph KBQueryWorkflow，
把图的状态结果归一成强类型 QueryResult / SSE 事件流。

职责：
  1. 构造 QueryGraphState（session_id / original_query / history / is_stream）
  2. 运行 LangGraph 查询图（同步图，经 asyncio.to_thread 桥接异步）
  3. 解析最终状态 -> answer / citations / refused / usage
  4. 异常归一：失败抛 QueryError（带 kind），由调用方（SSE 路由 / IM handler）转友好文案

约定：
  - 多轮上下文由外部调用方（IM 的 session.py / Web 前端）管理并传入 history；
    门面不持有会话状态，只负责单轮查询。
  - LangGraph 侧选型落定后，只需调整本文件内部对图的调用，SSE 协议与前端契约不变。

用法：
    from processor.query_processor.service import QueryService
    svc = QueryService()
    result = await svc.query(session_id, "员工每年有几天年假？", history=[...])
    async for ev in svc.stream_query(session_id, "再讲详细点", history=[...]):
        ...
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence

from processor.query_processor.main_graph import KBQueryWorkflow
from processor.query_processor.prompt.answer import REFUSAL_TEXT
from processor.query_processor.state import QueryGraphState


def _classify_error(exc: Exception) -> str:
    """把底层异常归类为 auth/rate/network/timeout/engine,供上层生成友好文案(BUG-4)。"""
    try:
        import openai
    except ImportError:  # noqa: BLE001
        openai = None  # type: ignore[assignment]
    seen: set = set()
    cur = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if openai is not None:
            if isinstance(cur, openai.AuthenticationError):
                return "auth"
            if isinstance(cur, openai.RateLimitError):
                return "rate"
            if isinstance(cur, openai.APITimeoutError):
                return "timeout"
            if isinstance(cur, openai.APIConnectionError):
                return "network"
        if isinstance(cur, TimeoutError):
            return "timeout"
        if isinstance(cur, ConnectionError):
            return "network"
        cur = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
    return "engine"

# ==================== 对外强类型契约 ====================


@dataclass
class Citation:
    """一条引用：指向某个文档的某一段原文，供 IM / Web 点击跳转 / 高亮。"""

    ref: str  # 【N】中的 N
    doc_name: str  # 文档名（带扩展名）
    snippet: str  # 原文片段
    url: str  # 点击跳转地址，如 /doc/{doc_id}?chunk={chunk_index}
    char_start: int = 0  # 在原文中的起止偏移（高亮定位）
    char_end: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "doc_name": self.doc_name,
            "snippet": self.snippet,
            "url": self.url,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class QueryResult:
    """一次问答的完整结果。"""

    answer: str
    citations: List[Citation] = field(default_factory=list)
    refused: bool = False
    tools_used: List[str] = field(default_factory=list)
    usage: LLMUsage = field(default_factory=LLMUsage)
    session_id: str = ""
    message_id: str = ""


@dataclass
class SSEEvent:
    """SSE 事件。type ∈ {status, tool, citation, delta, done, error}。"""

    type: str
    data: Dict[str, Any]


class QueryError(Exception):
    """门面异常，kind 用于上层生成友好文案（auth/rate/network/timeout/engine）。"""

    def __init__(self, message: str, kind: str = "engine"):
        super().__init__(message)
        self.kind = kind


# ==================== 引用解析 ====================

_CITE_RE = re.compile(r"[【\[](\d+)[】\]]")


def _looks_like_refusal(text: str) -> bool:
    """识别 LLM 生成的软拒答文案(说"没找到 / 未找到 / 无法回答"等),用于统一 refused 标志。"""
    s = (text or "").strip()
    if s.startswith(("文档未找到", "文档里没找到", "文档中未找到", "未找到相关", "没有找到相关", "无法回答")):
        return True
    return "没找到相关信息" in s or "未找到相关信息" in s or "未收录" in s


def _parse_citations(answer: str, sources: Sequence[dict]) -> List[Citation]:
    """把答案中的【N】标记映射到检索来源，生成可点击引用。"""
    citations: List[Citation] = []
    for match in _CITE_RE.finditer(answer):
        idx = int(match.group(1)) - 1
        if not (0 <= idx < len(sources)):
            continue
        src = sources[idx]
        doc_id = str(src.get("doc_id") or src.get("file_title") or src.get("doc_name") or "")
        doc_name = str(src.get("doc_name") or src.get("file_title") or "未知文档")
        chunk_index = src.get("chunk_index", 0)
        text = str(src.get("content") or src.get("text") or src.get("snippet") or "")
        citations.append(
            Citation(
                ref=str(idx + 1),
                doc_name=doc_name,
                snippet=text[:120],
                url=f"/doc/{doc_id}?chunk={chunk_index}",
                char_start=int(src.get("char_start") or 0),
                char_end=int(src.get("char_end") or 0),
            )
        )
    seen: set = set()
    unique: List[Citation] = []
    for c in citations:
        key = (c.url, c.ref)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


# ==================== 门面 ====================


class QueryService:
    """
    查询门面：唯一对外入口。

    参数：
        refusal_text: 拒答固定文案（检索不到时使用）。
        node_status_enabled: 是否把 LangGraph 逐节点执行作为 status 事件透出。
    """

    def __init__(self, refusal_text: str = "", node_status_enabled: bool = True):
        self._refusal_text = refusal_text or REFUSAL_TEXT
        self._node_status_enabled = node_status_enabled

    # ---------- 内部：运行 LangGraph 图 ----------

    @staticmethod
    def _build_state(session_id: str, message: str, history: List[dict], is_stream: bool) -> QueryGraphState:
        return {
            "session_id": session_id,
            "message_id": uuid.uuid4().hex,
            "original_query": message,
            "history": history,
            "is_stream": is_stream,
        }

    def _run_graph(
        self,
        session_id: str,
        message: str,
        history: List[dict],
        is_stream: bool,
        on_node: Optional[Any] = None,
        on_token: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """在（线程）上下文里跑同步图，返回最终聚合状态。on_node：节点完成回调；on_token：token 流式回调。"""
        wf = KBQueryWorkflow(on_token=on_token)
        init_state = self._build_state(session_id, message, history, is_stream)
        try:
            if is_stream:
                acc: Dict[str, Any] = dict(init_state)
                for item in wf.run(init_state, stream=True):
                    # langgraph 默认 stream_mode="updates"：{node_name: update_dict}
                    for node_name, update in item.items():
                        if on_node is not None:
                            on_node(node_name)
                        if isinstance(update, dict):
                            acc.update(update)
                return acc
            return wf.run(init_state, stream=False)
        except QueryError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise QueryError(f"查询管线执行失败: {exc}", kind=_classify_error(exc)) from exc

    # ---------- 对外：非流式（IM 用） ----------

    async def query(
        self,
        session_id: str,
        message: str,
        history: Optional[List[dict]] = None,
        user_id: str = "web",
        platform: str = "web",
    ) -> QueryResult:
        state = await asyncio.to_thread(self._run_graph, session_id, message, history or [], False)
        result = self._to_result(state, session_id)
        self._log_query(session_id, user_id, platform, message, result)
        return result

    # ---------- 对外：流式（Web SSE 用） ----------

    async def stream_query(
        self,
        session_id: str,
        message: str,
        history: Optional[List[dict]] = None,
        user_id: str = "web",
        platform: str = "web",
    ) -> AsyncIterator[SSEEvent]:
        """
        流式查询：产出 SSE 事件序列。
        - 节点执行 → status
        - answer_output 流式 token → delta(逐 token)
        - 非知识库路径(工具/拒答,整段返回)→ 结束前补一个 delta
        - 结束 → citation + done
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[SSEEvent] = asyncio.Queue()
        holder: Dict[str, Any] = {}
        streamed = {"tokens": False}

        def _on_node(node_name: str) -> None:
            if not self._node_status_enabled:
                return
            loop.call_soon_threadsafe(
                queue.put_nowait,
                SSEEvent("status", {"node": node_name, "message": f"正在执行 {node_name}"}),
            )

        def _on_token(text: str) -> None:
            if text:
                streamed["tokens"] = True
                loop.call_soon_threadsafe(queue.put_nowait, SSEEvent("delta", {"text": text}))

        async def _run() -> None:
            try:
                state = await asyncio.to_thread(
                    self._run_graph, session_id, message, history or [], True, _on_node, _on_token
                )
                holder["result"] = self._to_result(state, session_id)
                self._log_query(session_id, user_id, platform, message, holder["result"])
            except Exception as exc:  # noqa: BLE001
                holder["error"] = exc
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, SSEEvent("done", {"_end": True}))

        task = asyncio.create_task(_run())
        try:
            while True:
                event = await queue.get()
                if event.type == "done" and event.data.get("_end"):
                    break
                yield event
        finally:
            task.cancel()

        if "error" in holder:
            raise QueryError(f"查询管线执行失败: {holder['error']}", kind=_classify_error(holder["error"]))

        result: QueryResult = holder["result"]
        if result.citations:
            yield SSEEvent("citation", {"citations": [_c.to_dict() for _c in result.citations]})
        if not streamed["tokens"]:
            # 整段返回的路径(工具/拒答)补一个 delta
            yield SSEEvent("delta", {"text": result.answer})
        yield SSEEvent("done", self._result_payload(result))

    # ---------- 内部：状态 -> QueryResult ----------

    @staticmethod
    def _sources(state: Dict[str, Any]) -> List[dict]:
        for key in ("reranked_docs", "rrf_chunks", "embedding_chunks", "hyde_embedding_chunks"):
            value = state.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        return []

    @staticmethod
    def _log_query(session_id: str, user_id: str, platform: str, question: str, result: QueryResult) -> None:
        """写对话日志(后台 /logs 用,含 工具/引用/Token/拒答)。失败仅记日志,不影响主流程。"""
        try:
            from processor.db import insert_chat_log
            insert_chat_log({
                "session_id": session_id,
                "user_id": user_id,
                "platform": platform,
                "question": question,
                "answer": result.answer,
                "tools_used": result.tools_used,
                "citations": [c.to_dict() for c in result.citations],
                "tokens": result.usage.__dict__,
                "refused": result.refused,
            })
        except Exception as exc:  # noqa: BLE001
            logging.getLogger("query").warning(f"写对话日志失败: {exc}")

    def _to_result(self, state: Dict[str, Any], session_id: str) -> QueryResult:
        answer = str(state.get("answer") or "").strip()
        sources = self._sources(state)
        citations = _parse_citations(answer, sources)
        refused = bool(state.get("refused"))
        if not refused and not state.get("tools_used"):
            # 软拒答:检索到了资料但 LLM 判定无关而说"没找到" → 统一置 refused,保证标志一致
            if (not answer and not sources) or _looks_like_refusal(answer):
                refused = True
        if refused:
            answer = self._refusal_text
        elif not answer:
            answer = self._refusal_text
        usage = LLMUsage(
            prompt_tokens=int(state.get("prompt_tokens") or 0),
            completion_tokens=int(state.get("completion_tokens") or 0),
            total_tokens=int(state.get("total_tokens") or 0),
        )
        return QueryResult(
            answer=answer,
            citations=citations,
            refused=refused,
            tools_used=list(state.get("tools_used") or []),
            usage=usage,
            session_id=session_id,
            message_id=str(state.get("message_id") or ""),
        )

    @staticmethod
    def _result_payload(result: QueryResult) -> Dict[str, Any]:
        return {
            "answer": result.answer,
            "citations": [c.to_dict() for c in result.citations],
            "refused": result.refused,
            "tools_used": result.tools_used,
            "usage": result.usage.__dict__,
            "session_id": result.session_id,
            "message_id": result.message_id,
        }
