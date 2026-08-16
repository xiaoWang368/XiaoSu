"""引用解析 / 拒答识别 的单元测试(纯逻辑,无 LLM / 无外部依赖)。"""

from processor.query_processor.service import QueryService, _looks_like_refusal, _parse_citations


def test_parse_citations_maps_to_url():
    sources = [{
        "doc_id": "doc1", "doc_name": "员工手册.md", "chunk_index": 2,
        "content": "员工每年享有10天带薪年假", "char_start": 10, "char_end": 20,
    }]
    cites = _parse_citations("员工每年10天带薪年假【1】", sources)
    assert len(cites) == 1
    assert cites[0].doc_name == "员工手册.md"
    assert cites[0].url == "/doc/doc1?chunk=2"
    assert cites[0].snippet == "员工每年享有10天带薪年假"


def test_looks_like_refusal():
    assert _looks_like_refusal("文档未找到相关信息,换一种问法")
    assert _looks_like_refusal("未找到相关")
    assert not _looks_like_refusal("员工每年10天带薪年假")


def test_to_result_refused_when_no_sources():
    """检索空 → 拒答(门面层兜底)。"""
    svc = QueryService()
    result = svc._to_result({"answer": "", "reranked_docs": []}, "s")
    assert result.refused is True
    assert "文档未找到" in result.answer
