"""정확도 실험 러너 — 정답 만들기(가짜 포트)와 CLI 명령 모양(실행 안 함)."""
import json
import subprocess

import bench.run_bench as rb
from sgis_mcp.application.service import SgisService
from tests.fakes import YEARS, FakePort, MemorySink, ok

SIDO = ok("API_0301", [{"adm_cd": "38", "adm_nm": "경상남도", "tot_ppltn": "3000000"},
                       {"adm_cd": "11", "adm_nm": "서울특별시", "tot_ppltn": "9000000"}])
SGG38 = ok("API_0301", [{"adm_cd": "38111", "adm_nm": "창원시 의창구", "tot_ppltn": "200000"},
                        {"adm_cd": "38112", "adm_nm": "창원시 성산구", "tot_ppltn": "250000"},
                        {"adm_cd": "38113", "adm_nm": "창원시 마산합포구", "tot_ppltn": "180000"}])
SGG11 = ok("API_0301", [{"adm_cd": "11010", "adm_nm": "종로구", "tot_ppltn": "140000"}])
AGE = ok("API_0302", [{"adm_cd": "38112", "adm_nm": "창원시 성산구", "population": "40000"}])
AGE11 = ok("API_0302", [{"adm_cd": "11010", "adm_nm": "종로구", "population": "28000"}])


def test_make_truth_picks_middle_sigungu_and_computes_ratio():
    port = FakePort([("year/data.json", {}, YEARS), ("stats/population.json", {}, SIDO),
                     ("stats/population.json", {"adm_cd": "38"}, SGG38), ("stats/population.json", {"adm_cd": "11"}, SGG11),
                     ("stats/searchpopulation.json", {"adm_cd": "38112"}, AGE),
                     ("stats/searchpopulation.json", {"adm_cd": "11010"}, AGE11)])
    t = rb.make_truth(SgisService(port, MemorySink()), 2)
    ids = [q["id"] for q in t["questions"]]
    assert ids == ["11010-pop", "11010-65", "38112-pop", "38112-65"]  # 시도 코드순, 가운데 시군구
    q = {q["id"]: q for q in t["questions"]}
    assert q["38112-pop"]["truth"] == 250000 and q["38112-65"]["truth"] == 16.0
    assert "경상남도 창원시 성산구의 2024년 총인구" in q["38112-pop"]["question"]
    assert t["tr_ids"]


def test_ask_disables_builtin_tools_and_scopes_mcp(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["kw"] = kw
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"result": "답: 1", "num_turns": 1,
                                                               "modelUsage": {"m1": {}}}), "")

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    out = rb.ask("질문", "/tmp/mcp.json")
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == "" and "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--mcp-config") + 1] == "/tmp/mcp.json"
    assert seen["kw"]["stdin"] is subprocess.DEVNULL
    assert out["text"] == "답: 1" and out["models"] == ["m1"]
    rb.ask("질문")
    assert "--mcp-config" not in seen["cmd"]  # AI 단독 조건엔 MCP 없음
