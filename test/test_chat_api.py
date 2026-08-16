"""SSE 聊天接口测试:用 Mock QueryService(替换模块级 _svc),不依赖真实 API / PG。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from processor.query_processor.service import SSEEvent
from server.routes.chat import router


@pytest.fixture
def client(monkeypatch):
    class FakeService:
        async def stream_query(self, session_id, message, history=None, user_id="web", platform="web"):
            yield SSEEvent("status", {"message": "理解中"})
            yield SSEEvent("delta", {"text": "员工每年 10 天"})
            yield SSEEvent("done", {
                "answer": "员工每年 10 天", "citations": [], "refused": False,
                "tools_used": [], "usage": {}, "session_id": "s", "message_id": "m",
            })

    monkeypatch.setattr("server.routes.chat._svc", FakeService())
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_chat_sse_streams(client):
    r = client.post("/api/chat", json={"session_id": "s", "message": "员工每年有几天年假?"})
    assert r.status_code == 200
    assert "event: status" in r.text
    assert "event: delta" in r.text
    assert "event: done" in r.text


def test_chat_error_is_friendly(client, monkeypatch):
    class ErrService:
        async def stream_query(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("server.routes.chat._svc", ErrService())
    r = client.post("/api/chat", json={"session_id": "s", "message": "hi"})
    assert r.status_code == 200  # 不 500
    assert "event: error" in r.text
