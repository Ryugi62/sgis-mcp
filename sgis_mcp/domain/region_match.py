"""지명 → 지역 후보 매칭(순수 함수) — UC-2.

규칙: 질의를 토큰으로 나누고, 후보 이름의 각 토큰과 ①같음 ②시도 약칭(경남 …) ③접미(시·군·구·읍·면·동·가) 뗀 형태
④2자 이상 접두로 맞춘다. 점수가 가장 높은 후보들(동점 전부)을 돌려준다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence, Tuple

SIDO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
    "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원도": "강원",
    "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전북특별자치도": "전북",
    "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주", "제주도": "제주",
}
_SUFFIXES = ("특별자치시", "특별자치도", "특별시", "광역시", "시", "군", "구", "읍", "면", "동", "가", "리", "도")


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    full_name: str


def sido_short(name: str) -> str:
    if name in SIDO_SHORT:
        return SIDO_SHORT[name]
    for suf in ("특별자치시", "특별자치도", "특별시", "광역시", "도"):
        if name.endswith(suf) and len(name) > len(suf):
            return name[: -len(suf)]
    return name


def tokenize(query: str) -> List[str]:
    return [t for t in re.split(r"[\s,·/()]+", query or "") if t]


def _stem(tok: str) -> str:
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 1:
            return tok[: -len(suf)]
    return tok


def _token_score(q: str, name_tok: str) -> int:
    if q == name_tok:
        return 3
    if q == sido_short(name_tok) and q != name_tok:
        return 3
    if len(q) >= 2 and _stem(name_tok) == q:
        return 2
    if len(q) >= 2 and name_tok.startswith(q):
        return 1
    return 0


def match_regions(query: str, candidates: Sequence[Region]) -> List[Tuple[Region, List[str]]]:
    """가장 높은 점수의 후보(동점 전부)와 그 후보가 소비한 질의 토큰."""
    tokens = tokenize(query)
    squashed = "".join(tokens)
    scored = []
    for r in candidates:
        name_toks = tokenize(r.name)
        consumed: List[str] = []
        score = 0
        for q in tokens:
            best = max((_token_score(q, n) for n in name_toks), default=0)
            if best:
                score += best
                consumed.append(q)
        joined = "".join(name_toks)
        if score == 0 and len(joined) >= 2 and joined in squashed:
            score, consumed = 3 * len(name_toks), [joined]
        elif len(name_toks) > 1 and joined in squashed and len(consumed) < len(name_toks):
            score += 1
        if score:
            scored.append((score, r, consumed))
    if not scored:
        return []
    top = max(s for s, _, _ in scored)
    return [(r, c) for s, r, c in scored if s == top]
