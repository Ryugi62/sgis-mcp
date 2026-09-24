"""정확도 실험 채점(순수 함수) — AI가 말한 숫자를 SGIS 원값과 대조한다.

일치 기준(미리 고정): 인구수 = 상대오차 ≤ 0.5% · 비율(%) = 절대오차 ≤ 0.1%p.
"""
from __future__ import annotations

import re
from statistics import median
from typing import Dict, List, Optional

_ANS = re.compile(r"답\s*[:：]\s*(.+)")
_NUM = r"\d[\d,]*(?:\.\d+)?"
CITE_WORDS = ("SGIS", "trId", "국가데이터처", "통계청", "KOSIS", "인구주택총조사", "출처")


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def extract_number(text: str, kind: str) -> Optional[float]:
    """'답: …' 줄을 먼저 보고, 없으면 본문 첫 숫자. 만·천 단위와 % 처리."""
    if not text:
        return None
    m = _ANS.search(text)
    seg = m.group(1) if m else text
    if kind == "ratio":
        p = re.search(rf"({_NUM})\s*%", seg) or re.search(rf"({_NUM})", seg)
        return _to_float(p.group(1)) if p else None
    man = re.search(rf"({_NUM})\s*만(?:\s*({_NUM})\s*천)?(?:\s*({_NUM}))?", seg)
    if man:
        v = _to_float(man.group(1)) * 10000
        if man.group(2):
            v += _to_float(man.group(2)) * 1000
        elif man.group(3):
            v += _to_float(man.group(3))
        return v
    p = re.search(rf"({_NUM})", seg)
    return _to_float(p.group(1)) if p else None


def score(truth: float, answer_text: str, kind: str) -> Dict:
    got = extract_number(answer_text, kind)
    if got is None:
        return {"got": None, "exact": False, "err_pct": None, "cited": _cited(answer_text)}
    if kind == "ratio":
        err = abs(got - truth)
        exact = err <= 0.1
        err_pct = round(err / truth * 100, 2) if truth else None
    else:
        err_pct = round(abs(got - truth) / truth * 100, 2) if truth else None
        exact = err_pct is not None and err_pct <= 0.5
    return {"got": got, "exact": bool(exact), "err_pct": err_pct, "cited": _cited(answer_text)}


def _cited(text: str) -> bool:
    return any(w in (text or "") for w in CITE_WORDS)


def summarize(rows: List[Dict]) -> Dict:
    """rows: [{condition, exact, err_pct, cited}] → 조건별 집계."""
    out = {}
    for cond in sorted({r["condition"] for r in rows}):
        rs = [r for r in rows if r["condition"] == cond]
        errs = [r["err_pct"] for r in rs if r["err_pct"] is not None]
        out[cond] = {"n": len(rs), "exact": sum(r["exact"] for r in rs),
                     "median_err_pct": round(median(errs), 2) if errs else None,
                     "no_number": sum(r["err_pct"] is None for r in rs), "cited": sum(r["cited"] for r in rs)}
    return out
