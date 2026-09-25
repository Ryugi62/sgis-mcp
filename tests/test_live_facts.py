"""라이브 실측으로 확정한 SGIS 외부 사실(2026-09-25, 테스트키 실호출) — SPEC §6 「실측」 줄과 1:1.

- accessTimeout = 밀리초 epoch, 발급 시점 + 4시간(240분)  (문서 basics.html은 「초」라고 적혀 있다)
- errCd -100 = 「검색결과가 존재하지 않습니다.」 → 빈 결과(오류 아님)
- errCd -200 = 「검색할 주소를 확인해주세요」(지오코딩, 주소 판독 실패) → 도구 오류, SGIS 문구 그대로
- 응답 id: year/data.json = API_9902 · stats/searchpopulation.json = API_0312 (개발지원센터 문서 번호와 다르다)
"""
import json

import pytest

from sgis_mcp.adapters.sgis_gateway import SgisHttpGateway
from sgis_mcp.domain.errors import SgisApiError

ISSUED = 1790330953.0  # 라이브 발급 시각(초)
LIVE_TIMEOUT = "1790345353148"  # 라이브 accessTimeout 원값(밀리초) = 발급 + 240분


class Script:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def get(self, url, params, timeout):
        self.calls.append(url.rsplit("/", 1)[-1])
        status, body = self.script.pop(0)
        return status, json.dumps(body, ensure_ascii=False).encode("utf-8")


def auth(token):
    return (200, {"id": "API_0101", "errCd": 0, "errMsg": "Success", "trId": "U2p2_API_0101_1790330953146",
                  "result": {"accessToken": token, "accessTimeout": LIVE_TIMEOUT}})


def pop(tr):
    return (200, {"id": "API_0301", "errCd": 0, "errMsg": "Success", "trId": tr, "result": [{"adm_cd": "38"}]})


def test_live_access_timeout_is_epoch_ms_four_hours():
    clock = {"t": ISSUED}
    t = Script([auth("t1"), pop("p1"), pop("p2"), auth("t2"), pop("p3")])
    g = SgisHttpGateway(t, "K", "S", clock=lambda: clock["t"])
    g.call("stats/population.json", {"year": 1})
    clock["t"] = ISSUED + 230 * 60  # 230분 뒤: 아직 유효(만료 60초 전 여유 밖)
    g.call("stats/population.json", {"year": 2})
    assert t.calls == ["authentication.json", "population.json", "population.json"]
    clock["t"] = ISSUED + 240 * 60  # 240분 뒤: 만료 → 새로 받는다
    g.call("stats/population.json", {"year": 3})
    assert t.calls[-2:] == ["authentication.json", "population.json"]


def test_live_minus_100_message_is_empty_result():
    t = Script([auth("t1"), (200, {"id": "API_0301", "errCd": -100, "errMsg": "검색결과가 존재하지 않습니다.",
                                    "trId": "e_API_0301"})])
    r = SgisHttpGateway(t, "K", "S", clock=lambda: ISSUED).call("stats/population.json", {"adm_cd": "99999"})
    assert r.empty is True and r.result == []


def test_live_minus_200_bad_address_is_error_with_sgis_message():
    t = Script([auth("t1"), (200, {"id": "API_0707", "errCd": -200, "errMsg": "검색할 주소를 확인해주세요",
                                    "trId": "g_API_0707"})])
    g = SgisHttpGateway(t, "K", "S", clock=lambda: ISSUED)
    with pytest.raises(SgisApiError) as e:
        g.call("addr/geocodewgs84.json", {"address": "없는주소"})
    assert e.value.code == -200 and "검색할 주소를 확인해주세요" in str(e.value)


def test_fixtures_carry_live_response_ids():
    import os
    here = os.path.join(os.path.dirname(__file__), "fixtures")
    ids = {name: json.load(open(os.path.join(here, name), encoding="utf-8"))["id"]
           for name in ("year__data.json", "stats__searchpopulation.json", "stats__searchpopulation__adm_cd=38111.json")}
    assert ids == {"year__data.json": "API_9902", "stats__searchpopulation.json": "API_0312",
                   "stats__searchpopulation__adm_cd=38111.json": "API_0312"}
