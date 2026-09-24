"""행정구역코드 값 객체 — 시도 2 · 시군구 5 · 읍면동 7/8자리(SPEC §3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .errors import InvalidAdmCode

LEVELS = {2: "sido", 5: "sigungu", 7: "eupmyeondong", 8: "eupmyeondong"}
LEVEL_KO = {"sido": "시도", "sigungu": "시군구", "eupmyeondong": "읍면동"}


@dataclass(frozen=True)
class AdmCode:
    value: str

    @staticmethod
    def parse(raw) -> "AdmCode":
        s = str(raw).strip() if raw is not None else ""
        if not s.isdigit() or len(s) not in LEVELS:
            raise InvalidAdmCode(f"행정구역코드는 2(시도)·5(시군구)·7/8(읍면동)자리 숫자여야 합니다: {raw!r} — sgis_find_region으로 찾으세요")
        return AdmCode(s)

    @staticmethod
    def parse_optional(raw) -> Optional["AdmCode"]:
        if raw is None or str(raw).strip() == "":
            return None
        return AdmCode.parse(raw)

    @property
    def level(self) -> str:
        return LEVELS[len(self.value)]

    def parent(self) -> Optional["AdmCode"]:
        n = len(self.value)
        if n == 2:
            return None
        return AdmCode(self.value[:2] if n == 5 else self.value[:5])
