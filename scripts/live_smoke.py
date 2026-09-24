#!/usr/bin/env python3
"""라이브 검증(SPEC S7) — 인증키로 도구 12개를 실제 SGIS에 한 번씩 부르고 docs/live-check.md에 trId를 남긴다.

    python3 scripts/live_smoke.py --env-file ~/.config/sgis.env [--region "경남 창원시 의창구"]

비밀값(키·토큰)은 어디에도 쓰지 않는다. 결과 표는 활용 사례의 근거자료로 쓴다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from typing import Callable, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sgis_mcp.infrastructure.config import load_settings  # noqa: E402
from sgis_mcp.infrastructure.main import build  # noqa: E402


def scenario(region: str, address: str) -> List[Tuple[str, Callable[[dict], dict]]]:
    """(도구, 앞 결과 → 인자) 순서. 앞 단계 결과로 다음 인자를 만든다."""
    return [
        ("sgis_data_years", lambda ctx: {}),
        ("sgis_find_region", lambda ctx: {"query": region}),
        ("sgis_population_summary", lambda ctx: {"adm_cd": ctx["adm_cd"], "low_search": 1}),
        ("sgis_population_by_age", lambda ctx: {"adm_cd": ctx["adm_cd"], "age_type": "65세이상"}),
        ("sgis_households", lambda ctx: {"adm_cd": ctx["adm_cd"], "household_type": "1인가구"}),
        ("sgis_houses", lambda ctx: {"adm_cd": ctx["adm_cd"], "house_type": "아파트"}),
        ("sgis_industry_codes", lambda ctx: {}),
        ("sgis_companies", lambda ctx: {"adm_cd": ctx["adm_cd"][:2], "low_search": 1}),
        ("sgis_geocode", lambda ctx: {"address": address}),
        ("sgis_reverse_geocode", lambda ctx: {"lon": ctx.get("lon", 128.68), "lat": ctx.get("lat", 35.24)}),
        ("sgis_transform_coord", lambda ctx: {"x": ctx.get("lon", 128.68), "y": ctx.get("lat", 35.24)}),
        ("sgis_choropleth", lambda ctx: {"parent_adm_cd": ctx["adm_cd"], "age_type": "65세이상"}),
    ]


def run(server, region: str, address: str) -> List[dict]:
    ctx = {"adm_cd": None}
    rows = []
    for name, make in scenario(region, address):
        args = make(ctx)
        res = server.call(name, args)
        text = res["content"][0]["text"]
        row = {"tool": name, "args": args, "ok": not res["isError"], "tr_ids": [], "summary": ""}
        if res["isError"]:
            row["summary"] = text[:160]
        else:
            body = json.loads(text)
            cites = body.get("citations") or ([body["citation"]] if "citation" in body else [])
            row["tr_ids"] = [c.get("tr_id") for c in cites if c.get("tr_id")]
            row["fixture"] = any(c.get("fixture") for c in cites)
            if name == "sgis_find_region" and body.get("candidates"):
                ctx["adm_cd"] = body["candidates"][0]["adm_cd"]
                row["summary"] = f"{body['candidates'][0]['full_name']} → {ctx['adm_cd']}"
            elif name == "sgis_geocode" and body.get("results"):
                ctx["lon"], ctx["lat"] = body["results"][0]["lon"], body["results"][0]["lat"]
                row["summary"] = f"{body['results'][0]['address']} → ({ctx['lon']}, {ctx['lat']})"
            elif name == "sgis_choropleth":
                row["summary"] = f"{body['title']} · {len(body['rows'])}개 지역 → {os.path.basename(body['svg_path'])}"
                row["svg_path"] = body["svg_path"]
            elif "rows" in body:
                row["summary"] = f"{len(body['rows'])}행 · 기준연도 {body.get('year')}"
            elif "codes" in body:
                row["summary"] = f"{len(body['codes'])}개 코드 · {body.get('class_deg')}차"
            elif "latest" in body:
                row["summary"] = "최신 " + ", ".join(f"{k} {v}" for k, v in body["latest"].items() if v)
            elif "results" in body:
                row["summary"] = f"{len(body['results'])}건"
            elif "x" in body:
                row["summary"] = f"({body['x']}, {body['y']}) {body.get('srs')}"
        rows.append(row)
        if name == "sgis_find_region" and not ctx["adm_cd"]:
            break
    return rows


def to_markdown(rows: List[dict], when: str) -> str:
    ok = sum(r["ok"] for r in rows)
    fixture = any(r.get("fixture") for r in rows)
    lines = [f"# 라이브 검증 기록 — {when}", "",
             ("> ⚠ 가짜 응답(fixtures)으로 돌린 기록 — 실제 SGIS 호출 아님" if fixture else
              "> 실제 SGIS OpenAPI 호출(sgisapi.mods.go.kr). trId는 SGIS 쪽 거래번호다."), "",
             f"도구 {len(rows)}개 중 성공 {ok}개", "", "| # | 도구 | 결과 | trId |", "|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | `{r['tool']}` | {'✅' if r['ok'] else '❌'} {r['summary']} | {'<br>'.join('`' + t + '`' for t in r['tr_ids'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file")
    ap.add_argument("--fixtures")
    ap.add_argument("--region", default="경남 창원시 의창구")
    ap.add_argument("--address", default="경상남도 창원시 의창구 창원대학로 20")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs"))
    a = ap.parse_args(argv)
    settings = load_settings(a.env_file, fixtures=a.fixtures, out_dir=os.path.join(a.out, "img"))
    rows = run(build(settings), a.region, a.address)
    when = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    md = to_markdown(rows, when)
    name = "live-check-fixture.md" if a.fixtures else "live-check.md"
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
