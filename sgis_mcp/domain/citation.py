"""출처 — 모든 통계 결과에 붙는 인용 문구(SPEC S3)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

AGENCY = "국가데이터처 통계지리정보서비스(SGIS) OpenAPI"
PORTAL = "https://sgis.mods.go.kr"


@dataclass(frozen=True)
class Citation:
    survey: str
    year: Optional[int]
    api_id: Optional[str]
    tr_id: Optional[str]
    fixture: bool = False

    def text(self) -> str:
        parts = [f"출처: {AGENCY}", self.survey + (f" {self.year}년 기준" if self.year else "")]
        if self.api_id:
            parts.append(self.api_id)
        if self.tr_id:
            parts.append(f"trId {self.tr_id}")
        s = " · ".join(parts) + f" ({PORTAL})"
        if self.fixture:
            s = "[가짜 응답 — 테스트용, 실제 통계 아님] " + s
        return s

    def to_dict(self) -> dict:
        return {"agency": AGENCY, "survey": self.survey, "year": self.year, "api_id": self.api_id,
                "tr_id": self.tr_id, "fixture": self.fixture, "text": self.text()}
