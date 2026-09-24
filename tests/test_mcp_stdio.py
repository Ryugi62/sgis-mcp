"""MCP 서버를 실제 하위 프로세스(표준 입출력)로 띄워 JSON-RPC 왕복 — S1·S3·S8 + 부팅 검증."""
import json
import os
import subprocess
import sys
import time

from tests.conftest import FIXTURES, ROOT

EXPECTED_TOOLS = ["sgis_find_region", "sgis_data_years", "sgis_population_summary", "sgis_population_by_age",
                  "sgis_households", "sgis_houses", "sgis_companies", "sgis_industry_codes", "sgis_geocode",
                  "sgis_reverse_geocode", "sgis_transform_coord", "sgis_choropleth"]


def rpc(msgs, env_extra=None, args=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SGIS_")}
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, os.path.join(ROOT, "sgis_mcp_server.py")] + (args or []),
                       input="\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n",
                       capture_output=True, text=True, timeout=30, env=env, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]


INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}


def call(i, name, args):
    return {"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": name, "arguments": args}}


def body(o):
    return json.loads(o["result"]["content"][0]["text"])


def test_boot_initialize_list_twelve_tools_fast():
    t0 = time.perf_counter()
    out = rpc([INIT, {"jsonrpc": "2.0", "method": "notifications/initialized"},
               {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, {"jsonrpc": "2.0", "id": 3, "method": "nope"}])
    assert time.perf_counter() - t0 < 5  # 하위 프로세스 포함(서버 자체 초기화 < 1초 — S8)
    assert [o["id"] for o in out] == [1, 2, 3]  # 알림에는 응답 없음
    assert out[0]["result"]["serverInfo"]["name"] == "sgis-mcp"
    assert "citation" in out[0]["result"]["instructions"]
    assert [t["name"] for t in out[1]["result"]["tools"]] == EXPECTED_TOOLS
    assert out[2]["error"]["code"] == -32601


def test_without_keys_server_boots_and_explains():
    out = rpc([INIT, call(2, "sgis_population_summary", {"adm_cd": "11"})])
    r = out[1]["result"]
    assert r["isError"] is True and "SGIS_CONSUMER_KEY" in r["content"][0]["text"]


def test_fixture_mode_end_to_end_region_stats_map(tmp_path):
    out = rpc([INIT,
               call(2, "sgis_find_region", {"query": "경남 창원시 의창구 다동"}),
               call(3, "sgis_population_summary", {"adm_cd": "38111"}),
               call(4, "sgis_choropleth", {"parent_adm_cd": "38111", "age_type": "65세이상"}),
               call(5, "sgis_geocode", {"address": "대전 서구 청사로 189"}),
               call(6, "sgis_population_summary", {"adm_cd": "창원"})],
              args=["--fixtures", FIXTURES, "--out", str(tmp_path)],
              env_extra={"SGIS_MCP_LOG": str(tmp_path / "calls.jsonl")})
    region = body(out[1])
    assert region["candidates"][0]["adm_cd"] == "38111530"
    pop = body(out[2])
    assert pop["rows"][0]["tot_ppltn"] == 1000
    assert pop["citation"]["fixture"] is True and "가짜 응답" in pop["citation"]["text"]
    m = body(out[3])
    assert os.path.exists(m["svg_path"]) and m["svg_path"].startswith(str(tmp_path))
    assert {r["adm_cd"]: r["value"] for r in m["rows"]}["38111530"] == 30.0
    svg = open(m["svg_path"], encoding="utf-8").read()
    assert "가짜 응답" in svg and svg.count("<path") == 4
    assert body(out[4])["results"][0]["adm_cd"] == "25030600"
    assert out[5]["result"]["isError"] is True and "sgis_find_region" in out[5]["result"]["content"][0]["text"]
    log = [json.loads(l) for l in open(tmp_path / "calls.jsonl", encoding="utf-8")]
    kinds = {r["kind"] for r in log}
    assert kinds == {"api", "tool"}
    assert all("fixture-token" not in json.dumps(r) for r in log)
    assert any(r.get("trId") == "fx_API_0704" for r in log)


def test_every_stats_tool_result_carries_citation(tmp_path):
    names_args = [("sgis_data_years", {}), ("sgis_population_summary", {}), ("sgis_population_by_age", {"age_type": "24"}),
                  ("sgis_households", {}), ("sgis_houses", {}), ("sgis_companies", {}), ("sgis_industry_codes", {}),
                  ("sgis_geocode", {"address": "대전"}), ("sgis_reverse_geocode", {"lon": 127.38, "lat": 36.36}),
                  ("sgis_transform_coord", {"x": 127.38, "y": 36.36})]
    out = rpc([INIT] + [call(i + 2, n, a) for i, (n, a) in enumerate(names_args)],
              args=["--fixtures", FIXTURES, "--out", str(tmp_path)])
    for (name, _), o in zip(names_args, out[1:]):
        assert o["result"]["isError"] is False, (name, o)
        b = body(o)
        assert "citation" in b and b["citation"]["text"].startswith("[가짜 응답"), name


def test_fixture_single_dong_is_filtered_from_parent_file(tmp_path):
    out = rpc([INIT, call(2, "sgis_population_summary", {"adm_cd": "38111530"})],
              args=["--fixtures", FIXTURES, "--out", str(tmp_path)])
    rows = body(out[1])["rows"]
    assert [r["adm_cd"] for r in rows] == ["38111530"] and rows[0]["tot_ppltn"] == 3000
