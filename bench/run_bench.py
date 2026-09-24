#!/usr/bin/env python3
"""정확도 실험 — 같은 질문을 ①AI 단독 ②AI + SGIS MCP로 묻고 SGIS 원값과 대조한다(인증키 필요).

    python3 bench/run_bench.py --env-file ~/.config/sgis.env [--n-regions 10] [--model <이름>]

1) 정답: SGIS에서 직접 뽑는다(시도 코드순 앞 N개 시도마다 코드 중앙의 시군구 1곳 × 지표 2종 = 2N문항)
   - 총인구(stats/population) · 65세 이상 인구 비율 = 연령 24(65세이상) 인구 ÷ 총인구 × 100
2) 답: Claude Code CLI(`claude -p`), 내장 도구 전부 끔(--tools ""), 웹검색 없음.
   - llm 조건: MCP 없음 · mcp 조건: 이 저장소 서버만(--strict-mcp-config)
   - 두 조건의 질문 문장은 같다
3) 채점: bench/scoring.py(일치 기준은 실행 전에 고정 — 인구 ±0.5%, 비율 ±0.1%p)
결과: bench/out/{truth.json, answers.jsonl, summary.json, summary.md}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bench.scoring import score, summarize  # noqa: E402
from sgis_mcp.infrastructure.config import load_settings  # noqa: E402
from sgis_mcp.infrastructure.main import build  # noqa: E402

OUT = os.path.join(ROOT, "bench", "out")


def make_truth(service, n_regions: int) -> dict:
    years = service.data_years()
    y = years["latest"]["census"]
    sidos = service.population_summary(None, 1, y)
    tr = [sidos["citation"]["tr_id"]]
    qs = []
    for sido in sorted(sidos["rows"], key=lambda r: r["adm_cd"])[:n_regions]:
        sgg = service.population_summary(sido["adm_cd"], 1, y)
        rows = sorted((r for r in sgg["rows"] if isinstance(r.get("tot_ppltn"), (int, float))), key=lambda r: r["adm_cd"])
        if not rows:
            continue
        pick = rows[len(rows) // 2]
        age = service.population_by_age(pick["adm_cd"], 0, y, "24", 0)
        tr += [sgg["citation"]["tr_id"], age["citation"]["tr_id"]]
        a65 = age["rows"][0]["population"] if age["rows"] else None
        name = f"{sido['adm_nm']} {pick['adm_nm']}"
        qs.append({"id": f"{pick['adm_cd']}-pop", "region": name, "adm_cd": pick["adm_cd"], "kind": "count",
                   "truth": pick["tot_ppltn"], "question": f"{name}의 {y}년 총인구는 몇 명인가요?"})
        if a65 is not None and pick["tot_ppltn"]:
            qs.append({"id": f"{pick['adm_cd']}-65", "region": name, "adm_cd": pick["adm_cd"], "kind": "ratio",
                       "truth": round(a65 / pick["tot_ppltn"] * 100, 2),
                       "question": f"{name}의 {y}년 65세 이상 인구 비율은 몇 %인가요?"})
    return {"year": y, "questions": qs, "tr_ids": [t for t in tr if t],
            "rule": "인구 상대오차 ≤ 0.5% · 비율 절대오차 ≤ 0.1%p", "source": "국가데이터처 SGIS OpenAPI"}


PROMPT = "{q} 마지막 줄에 '답: <숫자>' 형식으로 숫자 하나만 쓰세요. 근거나 출처가 있으면 그 위에 적으세요."


def ask(question: str, mcp_config: str = None, model: str = None, timeout: int = 240) -> dict:
    cwd = tempfile.mkdtemp(prefix="sgis-bench-")
    cmd = ["claude", "-p", PROMPT.format(q=question), "--output-format", "json", "--tools", "", "--strict-mcp-config"]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config, "--allowedTools", "mcp__sgis"]
    if model:
        cmd += ["--model", model]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    try:
        d = json.loads(p.stdout)
    except ValueError:
        return {"text": "", "error": (p.stderr or p.stdout)[-300:], "sec": round(time.time() - t0, 1)}
    return {"text": d.get("result") or "", "sec": round(time.time() - t0, 1), "turns": d.get("num_turns"),
            "models": sorted((d.get("modelUsage") or {}).keys())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", required=True)
    ap.add_argument("--n-regions", type=int, default=10)
    ap.add_argument("--model")
    a = ap.parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    settings = load_settings(a.env_file, out_dir=os.path.join(OUT, "maps"))
    if not settings.consumer_key:
        sys.exit("인증키 없음 — --env-file에 SGIS_CONSUMER_KEY/SGIS_CONSUMER_SECRET")
    truth = make_truth(build(settings).service, a.n_regions)
    json.dump(truth, open(os.path.join(OUT, "truth.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    mcp = os.path.join(OUT, "mcp.json")
    json.dump({"mcpServers": {"sgis": {"command": sys.executable,
                                       "args": [os.path.join(ROOT, "sgis_mcp_server.py"), "--env-file",
                                                os.path.abspath(a.env_file), "--out", os.path.join(OUT, "maps")],
                                       "env": {"SGIS_MCP_LOG": os.path.join(OUT, "calls.jsonl")}}}},
              open(mcp, "w", encoding="utf-8"))
    rows = []
    with open(os.path.join(OUT, "answers.jsonl"), "w", encoding="utf-8") as f:
        for q in truth["questions"]:
            for cond, cfg in (("llm", None), ("mcp", mcp)):
                ans = ask(q["question"], cfg, a.model)
                sc = score(q["truth"], ans["text"], q["kind"])
                row = dict(q, condition=cond, answer=ans, **sc)
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                print(cond, q["id"], q["truth"], "→", sc["got"], "✓" if sc["exact"] else "✗", flush=True)
    s = summarize(rows)
    models = sorted({m for r in rows for m in (r["answer"].get("models") or [])})
    summary = {"year": truth["year"], "n_questions": len(truth["questions"]), "rule": truth["rule"],
               "models": models, "by_condition": s}
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = [f"# 정확도 실험 — {time.strftime('%Y-%m-%d %H:%M')}", "",
          f"질문 {len(truth['questions'])}개(기준연도 {truth['year']}) · 일치 기준 {truth['rule']} · 모델 {', '.join(models)}", "",
          "| 조건 | 원값 일치 | 오차 중앙값 | 숫자 없음 | 출처 표기 |", "|---|---|---|---|---|"]
    for cond, v in s.items():
        md.append(f"| {'AI 단독' if cond == 'llm' else 'AI + SGIS MCP'} | {v['exact']}/{v['n']} | {v['median_err_pct']}% | "
                  f"{v['no_number']} | {v['cited']}/{v['n']} |")
    md += ["", "정답 trId: " + ", ".join(f"`{t}`" for t in truth["tr_ids"][:6]) + (" …" if len(truth["tr_ids"]) > 6 else "")]
    open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
