"""SGIS OpenAPI 게이트웨이 — SgisPort 구현. 토큰 캐시 · -401 재인증 1회 · 오류 매핑(SPEC §6·§8).

전송(Transport)은 포트로 받는다: 실제 urllib 구현과 가짜 응답 구현은 infrastructure에 있다.
"""
from __future__ import annotations

import json
import re
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple

try:
    from typing import Protocol
except ImportError:  # pragma: no cover
    Protocol = object  # type: ignore

from ..application.ports import ApiResponse
from ..domain.errors import NotConfigured, SgisApiError, SgisAuthError

DEFAULT_BASE = "https://sgisapi.mods.go.kr/OpenAPI3"
AUTH_PATH = "auth/authentication.json"


class Transport(Protocol):
    def get(self, url: str, params: Dict[str, str], timeout: float) -> Tuple[int, bytes]:
        ...


def _clean(params: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for k, v in params.items():
        if v is None or v == "":
            continue
        out[k] = str(v)
    return out


def _rows(result: Any) -> int:
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        rd = result.get("resultdata")
        return len(rd) if isinstance(rd, list) else 1
    return 0


class SgisHttpGateway:
    def __init__(self, transport: Transport, consumer_key: str, consumer_secret: str, base_url: str = DEFAULT_BASE,
                 timeout: float = 20.0, clock: Callable[[], float] = time.time,
                 on_call: Optional[Callable[[dict], None]] = None):
        self.transport, self.key, self.secret = transport, consumer_key or "", consumer_secret or ""
        self.base = base_url.rstrip("/")
        self.timeout, self.clock, self.on_call = timeout, clock, on_call
        self._token: Optional[str] = None
        self._expires: float = 0.0
        self._cache: "OrderedDict[tuple, ApiResponse]" = OrderedDict()  # 같은 요청은 SGIS에 다시 보내지 않는다(부하 최소화)
        self.cache_size = 256

    # ------------------------------------------------------------------
    def _get_json(self, path: str, params: Dict[str, str]) -> Tuple[dict, float]:
        t0 = time.perf_counter()
        status, body = self.transport.get(f"{self.base}/{path}", params, self.timeout)
        ms = (time.perf_counter() - t0) * 1000
        text = body.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except ValueError:
            plain = re.sub(r"<[^>]+>", " ", text)
            plain = re.sub(r"\s+", " ", plain).strip()[:200]
            self._log(path, None, None, ms, False, -1, status)
            raise SgisApiError(f"HTTP {status}", plain or "JSON이 아닌 응답")
        if not isinstance(data, dict):
            raise SgisApiError(f"HTTP {status}", "예상하지 못한 응답 형식")
        return data, ms

    def _log(self, path, api_id, tr_id, ms, ok, rows, err) -> None:
        if self.on_call:
            self.on_call({"kind": "api", "path": path, "api": api_id, "trId": tr_id, "ms": round(ms, 1), "ok": ok,
                          "rows": rows, "errCd": err})

    def _authenticate(self) -> str:
        data, ms = self._get_json(AUTH_PATH, {"consumer_key": self.key, "consumer_secret": self.secret})
        err = data.get("errCd", 0)
        self._log(AUTH_PATH, data.get("id"), data.get("trId"), ms, err == 0, 0, err)
        if err != 0:
            raise SgisAuthError(err, data.get("errMsg", "인증 실패") +
                                " — 개발지원센터 인증키(서비스 ID·보안 Key)를 확인하세요", data.get("id"), data.get("trId"))
        res = data.get("result") or {}
        token = res.get("accessToken")
        if not token:
            raise SgisAuthError(err, "accessToken이 없습니다", data.get("id"), data.get("trId"))
        try:
            exp = float(res.get("accessTimeout"))
            exp = exp / 1000.0 if exp > 1e12 else exp
        except (TypeError, ValueError):
            exp = self.clock() + 3600
        self._token, self._expires = token, exp
        return token

    def _access_token(self) -> str:
        if self._token and self.clock() < self._expires - 60:
            return self._token
        return self._authenticate()

    def _remember(self, key: tuple, resp: ApiResponse) -> ApiResponse:
        self._cache[key] = resp
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return resp

    # SgisPort ---------------------------------------------------------
    def call(self, path: str, params: Dict[str, Any]) -> ApiResponse:
        if not self.key or not self.secret:
            raise NotConfigured("SGIS 인증키가 없습니다 — 환경변수 SGIS_CONSUMER_KEY(서비스 ID)·SGIS_CONSUMER_SECRET(보안 Key)를 "
                                "설정하세요. 발급: https://sgis.mods.go.kr/developer (테스트키 신청 즉시 발급)")
        clean = _clean(params)
        key = (path, tuple(sorted(clean.items())))
        if key in self._cache:
            self._cache.move_to_end(key)
            hit = self._cache[key]
            if self.on_call:
                self.on_call({"kind": "api", "path": path, "api": hit.api_id, "trId": hit.tr_id, "ms": 0.0, "ok": True,
                              "rows": _rows(hit.result), "errCd": 0, "cached": True})
            return hit
        for attempt in (1, 2):
            token = self._access_token()
            data, ms = self._get_json(path, dict(clean, accessToken=token))
            err = data.get("errCd", 0)
            api_id, tr_id = data.get("id"), data.get("trId")
            fixture = "_fixture" in data
            if err == 0:
                resp = ApiResponse(data=data, api_id=api_id, tr_id=tr_id, fixture=fixture)
                self._log(path, api_id, tr_id, ms, True, _rows(resp.result), 0)
                return self._remember(key, resp)
            self._log(path, api_id, tr_id, ms, False, 0, err)
            if err == -401 and attempt == 1:
                self._token = None
                continue
            if err == -100:
                return self._remember(key, ApiResponse(data={"result": []}, api_id=api_id, tr_id=tr_id,
                                                       fixture=fixture, empty=True))
            raise SgisApiError(err, data.get("errMsg", ""), api_id, tr_id)
        raise SgisApiError(-401, "재인증 후에도 인증 실패")  # pragma: no cover
