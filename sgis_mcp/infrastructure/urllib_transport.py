"""실제 HTTP 전송 — 표준 라이브러리 urllib만(설치 0)."""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Tuple

from .. import __version__


class UrllibTransport:
    def get(self, url: str, params: Dict[str, str], timeout: float) -> Tuple[int, bytes]:
        full = url + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(full, headers={"User-Agent": f"sgis-mcp/{__version__}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read() or b""
