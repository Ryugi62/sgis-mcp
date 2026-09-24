"""도메인 오류 어휘."""
from __future__ import annotations

from typing import Optional


class SgisError(Exception):
    """sgis-mcp의 모든 오류."""


class InvalidAdmCode(SgisError):
    pass


class InvalidArgument(SgisError):
    pass


class NotConfigured(SgisError):
    pass


class SgisApiError(SgisError):
    def __init__(self, code, message: str, api_id: Optional[str] = None, tr_id: Optional[str] = None):
        self.code, self.message, self.api_id, self.tr_id = code, message, api_id, tr_id
        super().__init__(f"SGIS 오류 {code}: {message}" + (f" ({api_id}, trId {tr_id})" if api_id or tr_id else ""))


class SgisAuthError(SgisApiError):
    pass
