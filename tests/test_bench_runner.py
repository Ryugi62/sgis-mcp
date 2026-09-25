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
AGE = ok("API_0312", [{"adm_cd": "38112", "adm_nm": "창원시 성산구", "population": "40000"}])
AGE11 = ok("API_0312", [{"adm_cd": "11010", "adm_nm": "종로구", "population": "28000"}])


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


def test_ask_runs_in_empty_dir_under_bench_out_not_system_temp(monkeypatch):
    # 2026-09-25 실측: 시스템 임시 폴더(/var/folders/…)를 cwd로 주면 claude -p가 이 질문에서 응답 없이 멈췄다(3/3 시간 초과),
    # 같은 질문을 다른 빈 폴더에서 돌리면 10초 안팎에 끝났다 → 빈 작업 폴더는 bench/out/cwd 아래에 만든다.
    seen = {}

    def fake_run(cmd, **kw):
        seen["cwd"] = kw["cwd"]
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"result": "답: 1"}), "")

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    rb.ask("질문")
    import os
    assert os.path.dirname(seen["cwd"]) == os.path.join(rb.OUT, "cwd") and os.listdir(seen["cwd"]) == []


def test_ask_timeout_is_recorded_not_fatal(monkeypatch):
    def fake_run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))

    monkeypatch.setattr(rb.subprocess, "run", fake_run)
    out = rb.ask("질문", timeout=5)
    assert out["text"] == "" and "timeout" in out["error"]


def test_rescore_recomputes_from_saved_answers(tmp_path):
    ans = tmp_path / "answers.jsonl"
    rows = [{"id": "q1", "kind": "count", "truth": 100, "condition": "llm",
             "answer": {"text": "SGIS에서 확인\n답: 90", "models": ["m"]}, "got": 90, "exact": False, "err_pct": 10.0, "cited": True},
            {"id": "q1", "kind": "count", "truth": 100, "condition": "mcp",
             "answer": {"text": "trId ab_API_0301_1790331623987\n답: 100", "models": ["m"]}}]
    ans.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    s = rb.rescore(str(ans))
    assert s["llm"]["exact"] == 0 and s["llm"]["tr_cited"] == 0
    assert s["mcp"]["exact"] == 1 and s["mcp"]["tr_cited"] == 1
