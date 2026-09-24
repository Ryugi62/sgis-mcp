"""정확도 실험 채점 — 숫자 추출·일치 기준(미리 고정)·집계."""
import pytest

from bench.scoring import extract_number, score, summarize


@pytest.mark.parametrize("text,kind,want", [
    ("답: 148,920", "count", 148920), ("약 25만 명입니다.\n답: 25만", "count", 250000),
    ("답: 58만 5천 명", "count", 585000), ("답: 12만 3456명", "count", 123456),
    ("65세 이상 비율은 약 18.4%입니다. 답: 18.4%", "ratio", 18.4), ("답: 21", "ratio", 21.0),
    ("잘 모르겠습니다", "count", None), ("인구는 1,234명", "count", 1234)])
def test_extract_number(text, kind, want):
    assert extract_number(text, kind) == want


def test_count_exact_within_half_percent():
    assert score(100000, "답: 100400", "count")["exact"] is True
    r = score(100000, "답: 101000", "count")
    assert r["exact"] is False and r["err_pct"] == 1.0


def test_ratio_exact_within_point_one():
    assert score(18.43, "답: 18.4%", "ratio")["exact"] is True
    assert score(18.43, "답: 18.6%", "ratio")["exact"] is False


def test_cited_detection():
    assert score(1, "답: 1 (출처: 국가데이터처 SGIS · trId x)", "count")["cited"] is True
    assert score(1, "답: 1", "count")["cited"] is False


def test_summarize_by_condition():
    rows = [{"condition": "llm", "exact": False, "err_pct": 4.0, "cited": False},
            {"condition": "llm", "exact": True, "err_pct": 0.1, "cited": False},
            {"condition": "mcp", "exact": True, "err_pct": 0.0, "cited": True},
            {"condition": "mcp", "exact": True, "err_pct": None, "cited": True}]
    s = summarize(rows)
    assert s["llm"] == {"n": 2, "exact": 1, "median_err_pct": 2.05, "no_number": 0, "cited": 0}
    assert s["mcp"]["exact"] == 2 and s["mcp"]["no_number"] == 1 and s["mcp"]["cited"] == 2
