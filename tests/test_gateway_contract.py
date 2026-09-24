"""SGIS HTTP 게이트웨이 계약 — 가짜 전송(네트워크 0). S4·§6·§8."""
import json

import pytest

from sgis_mcp.adapters.sgis_gateway import DEFAULT_BASE, SgisHttpGateway
from sgis_mcp.domain.errors import NotConfigured, SgisApiError, SgisAuthError


class FakeTransport:
    def __init__(self, script):
        self.script = list(script)  # 호출 순서대로 (status, body_obj_or_str)
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, dict(params)))
        status, body = self.script.pop(0)
        return status, (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode("utf-8")


AUTH_OK = (200, {"id": "API_0101", "errCd": 0, "errMsg": "Success", "trId": "a",
                 "result": {"accessToken": "tok-1", "accessTimeout": "1790240000000"}})
AUTH_OK2 = (200, {"id": "API_0101", "errCd": 0, "errMsg": "Success", "trId": "a2",
                  "result": {"accessToken": "tok-2", "accessTimeout": "1790240000000"}})
POP_OK = (200, {"id": "API_0301", "errCd": 0, "errMsg": "Success", "trId": "p1", "result": [{"adm_cd": "11"}]})
EXPIRED = (200, {"errCd": -401, "errMsg": "인증 정보가 존재하지 않습니다", "id": "API_0301", "trId": "x"})
NOW = lambda: 1790224000.0  # 초


def gw(script, log=None, **kw):
    t = FakeTransport(script)
    return SgisHttpGateway(t, "KEY", "SECRET", clock=NOW, on_call=log, **kw), t


def test_default_base_is_mods_domain():
    assert DEFAULT_BASE == "https://sgisapi.mods.go.kr/OpenAPI3"


def test_authenticates_once_and_reuses_token():
    g, t = gw([AUTH_OK, POP_OK, POP_OK])
    r1 = g.call("stats/population.json", {"year": 2024, "adm_cd": None})
    g.call("stats/population.json", {"year": 2023})
    assert [u.rsplit("/", 1)[-1] for u, _ in t.calls] == ["authentication.json", "population.json", "population.json"]
    assert t.calls[0][1] == {"consumer_key": "KEY", "consumer_secret": "SECRET"}
    assert t.calls[1][1]["accessToken"] == "tok-1" and "adm_cd" not in t.calls[1][1]  # None 파라미터는 뺀다
    assert r1.api_id == "API_0301" and r1.tr_id == "p1" and r1.result == [{"adm_cd": "11"}]


def test_reauth_once_on_401_then_succeeds():
    g, t = gw([AUTH_OK, EXPIRED, AUTH_OK2, POP_OK])
    r = g.call("stats/population.json", {"year": 2024})
    assert r.tr_id == "p1" and t.calls[-1][1]["accessToken"] == "tok-2"


def test_second_401_is_an_error():
    g, _ = gw([AUTH_OK, EXPIRED, AUTH_OK2, EXPIRED])
    with pytest.raises(SgisApiError) as e:
        g.call("stats/population.json", {"year": 2024})
    assert e.value.code == -401


def test_auth_failure_raises_auth_error():
    g, _ = gw([(200, {"errCd": -401, "errMsg": "인증정보가 존재하지 않습니다", "id": "API_0101", "trId": "z"})])
    with pytest.raises(SgisAuthError):
        g.call("stats/population.json", {"year": 2024})


def test_no_result_minus_100_is_empty_not_error():
    g, _ = gw([AUTH_OK, (200, {"errCd": -100, "errMsg": "검색결과가 존재하지 않습니다", "id": "API_0301", "trId": "e"})])
    r = g.call("stats/population.json", {"year": 2024})
    assert r.empty is True and r.result == [] and r.tr_id == "e"


def test_html_error_body_becomes_api_error():
    g, _ = gw([AUTH_OK, (200, "<html><head><title>Error</title></head><body>필수 파라미터 누락</body></html>")])
    with pytest.raises(SgisApiError) as e:
        g.call("stats/population.json", {})
    assert "필수 파라미터 누락" in str(e.value)


def test_token_refreshes_after_expiry():
    clock = {"t": 1790224000.0}
    t = FakeTransport([(200, {"errCd": 0, "id": "API_0101", "result": {"accessToken": "old", "accessTimeout": str(int((1790224000 + 100) * 1000))}}),
                       POP_OK, AUTH_OK2, POP_OK])
    g = SgisHttpGateway(t, "K", "S", clock=lambda: clock["t"])
    g.call("stats/population.json", {"year": 1})
    clock["t"] += 90  # 만료 60초 전 여유 안쪽 → 새로 받는다
    g.call("stats/population.json", {"year": 2})
    assert t.calls[-1][1]["accessToken"] == "tok-2"


def test_missing_keys_raise_not_configured():
    g = SgisHttpGateway(FakeTransport([]), "", "", clock=NOW)
    with pytest.raises(NotConfigured) as e:
        g.call("stats/population.json", {})
    assert "SGIS_CONSUMER_KEY" in str(e.value)


def test_call_log_has_trid_and_no_secrets():
    records = []
    g, _ = gw([AUTH_OK, POP_OK], log=records.append)
    g.call("stats/population.json", {"year": 2024})
    dumped = json.dumps(records, ensure_ascii=False)
    assert "tok-1" not in dumped and "SECRET" not in dumped and "KEY" not in dumped
    api = [r for r in records if r["path"] == "stats/population.json"][0]
    assert api["trId"] == "p1" and api["ok"] is True and api["rows"] == 1 and api["ms"] >= 0


def test_fixture_marker_sets_flag():
    g, _ = gw([AUTH_OK, (200, {"errCd": 0, "id": "API_0301", "trId": "f", "result": [], "_fixture": "synthetic"})])
    assert g.call("stats/population.json", {"year": 1}).fixture is True


def test_identical_request_served_from_cache_without_sgis_call():
    records = []
    g, t = gw([AUTH_OK, POP_OK], log=records.append)
    a = g.call("stats/population.json", {"year": 2024, "adm_cd": "11"})
    b = g.call("stats/population.json", {"adm_cd": "11", "year": 2024})  # 순서만 다른 같은 요청
    assert a is b and len(t.calls) == 2  # 인증 1 + 조회 1
    assert records[-1]["cached"] is True and records[-1]["trId"] == "p1"


def test_cache_is_bounded():
    g, t = gw([AUTH_OK] + [POP_OK] * 3)
    g.cache_size = 2
    for i in range(3):
        g.call("stats/population.json", {"year": i})
    assert len(g._cache) == 2
