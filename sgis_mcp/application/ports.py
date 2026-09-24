"""포트 — 바깥(SGIS HTTP·파일)과의 경계. 구현은 adapters/infrastructure에 있다."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    from typing import Protocol
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore


@dataclass
class ApiResponse:
    data: Dict[str, Any]
    api_id: Optional[str] = None
    tr_id: Optional[str] = None
    fixture: bool = False
    empty: bool = False

    @property
    def result(self) -> Any:
        if "result" in self.data:
            return self.data.get("result")
        return self.data.get("features")


class SgisPort(Protocol):
    def call(self, path: str, params: Dict[str, Any]) -> ApiResponse:
        ...


class FileSink(Protocol):
    def write_text(self, name: str, text: str) -> str:
        ...
