"""answer_output 节点测试:拒答(不调 LLM)+ RAG / 闲聊(Mock LLM,不依赖真实 API)。"""

from processor.query_processor.nodes.g_node_answer_output import NodeAnswerOutput


def test_hard_refusal_no_llm():
    """检索空/低分 → 硬拒答,不调用 LLM。"""
    node = NodeAnswerOutput()
    out = node({
        "original_query": "我们公司CEO的家庭住址是?", "intent": "knowledge",
        "reranked_docs": [], "answer": "",
    })
    assert out["refused"] is True
    assert "文档未找到" in out["answer"]


def test_rag_with_mock_llm(monkeypatch):
    """RAG 路径:MOCK LLM(替换 _stream_answer),断言答案 + token 用量。"""
    node = NodeAnswerOutput()

    def fake_stream(messages):
        return (
            "员工每年享有 10 天带薪年假【1】",
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    monkeypatch.setattr(node, "_stream_answer", fake_stream)
    out = node({
        "original_query": "员工每年有几天年假?", "intent": "knowledge", "answer": "",
        "reranked_docs": [{
            "doc_id": "d1", "doc_name": "员工手册.md", "score": 0.5,
            "content": "员工每年享有10天带薪年假",
        }],
    })
    assert "10 天" in out["answer"]
    assert out["total_tokens"] == 15
    assert out["prompt_tokens"] == 10


def test_chat_with_mock_llm(monkeypatch):
    """闲聊路径:MOCK LLM,不拒答、不查文档。"""
    node = NodeAnswerOutput()

    def fake_stream(messages):
        return (
            "你好!我是小苏,可以帮你查公司文档和系统数据。",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    monkeypatch.setattr(node, "_stream_answer", fake_stream)
    out = node({
        "original_query": "你好,你能帮我做什么?", "intent": "chat", "answer": "",
        "reranked_docs": [],
    })
    assert "小苏" in out["answer"]
    assert out["refused"] is False
