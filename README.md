# sgis-mcp — AI 대화 안에서 부르는 SGIS

[![test](https://github.com/Ryugi62/sgis-mcp/actions/workflows/test.yml/badge.svg)](https://github.com/Ryugi62/sgis-mcp/actions/workflows/test.yml)

**국가데이터처 통계지리정보서비스(SGIS) OpenAPI**를 생성형 AI 도구(MCP)로 여는 서버입니다.
Claude · Codex · Gemini CLI 같은 AI에게 「창원시 의창구 읍면동별 65세 이상 인구 비율 지도 그려 줘」라고 말하면,
AI가 기억으로 지어내지 않고 SGIS에서 **원값을 조회해 출처(조사명·기준연도·SGIS 거래번호 trId)와 함께** 답합니다.

- 설치 0 — 파이썬 3.9+ 표준 라이브러리만 씁니다(pip 설치 없음).
- 지명 한 줄 → 행정구역코드(시도·시군구·읍면동) → 통계 → 단계구분도(SVG)까지 한 대화에서.
- 모든 통계 결과에 `citation`(국가데이터처 SGIS · 조사명 · 기준연도 · API id · trId)이 붙습니다.

## 도구 12개

| 도구 | 하는 일 | SGIS API |
|---|---|---|
| `sgis_find_region` | 지명 → 행정구역코드(「경남 창원시 의창구 팔용동」) | `addr/stage` (+ `addr/geocodewgs84`) |
| `sgis_data_years` | 최신·전체 기준연도 | `year/data` |
| `sgis_population_summary` | 총조사 주요지표(총인구·평균나이·인구밀도·노령화지수 …) | `stats/population` |
| `sgis_population_by_age` | 연령·성별 인구(예: 65세 이상 여성) | `stats/searchpopulation` |
| `sgis_households` | 가구수(예: 1인가구) | `stats/household` |
| `sgis_houses` | 주택수(예: 아파트) | `stats/house` |
| `sgis_companies` | 사업체수·종사자수(산업분류별) | `stats/company` |
| `sgis_industry_codes` | 산업분류 코드(연도로 8~11차 자동) | `stats/industrycode` |
| `sgis_geocode` | 주소 → WGS84 경위도 + 행정동 코드 | `addr/geocodewgs84` |
| `sgis_reverse_geocode` | 경위도 → 주소·행정동 코드 | `addr/rgeocodewgs84` |
| `sgis_transform_coord` | 좌표계 변환(4326 ↔ 5179 …) | `transformation/transcoord` |
| `sgis_choropleth` | 하위 지역 단계구분도 SVG(5분위·범례·출처 줄) | `boundary/hadmarea` + `stats/*` |

## 설치 — 3줄

1. **인증키**: [SGIS 개발지원센터](https://sgis.mods.go.kr/developer) 회원가입 → 인증키 신청(테스트키는 신청 즉시 발급, 무료).
2. **내려받기**: `git clone https://github.com/Ryugi62/sgis-mcp`
3. **AI 도구에 등록**(하나만 고르세요):

```bash
# Claude Code
claude mcp add sgis -e SGIS_CONSUMER_KEY=서비스ID -e SGIS_CONSUMER_SECRET=보안Key -- python3 /경로/sgis-mcp/sgis_mcp_server.py
# Codex CLI
codex mcp add sgis --env SGIS_CONSUMER_KEY=서비스ID --env SGIS_CONSUMER_SECRET=보안Key -- python3 /경로/sgis-mcp/sgis_mcp_server.py
# Gemini CLI
gemini mcp add sgis -e SGIS_CONSUMER_KEY=서비스ID -e SGIS_CONSUMER_SECRET=보안Key python3 /경로/sgis-mcp/sgis_mcp_server.py
```

Claude Desktop은 설정 파일 `claude_desktop_config.json`에:

```json
{"mcpServers": {"sgis": {"command": "python3", "args": ["/경로/sgis-mcp/sgis_mcp_server.py"],
  "env": {"SGIS_CONSUMER_KEY": "서비스ID", "SGIS_CONSUMER_SECRET": "보안Key"}}}}
```

키를 파일로 두려면 `--env-file /경로/sgis.env`(내용: `SGIS_CONSUMER_KEY=…` 두 줄)를 인자로 주세요.
지도 SVG는 `~/sgis-mcp-maps/`(바꾸려면 `--out` 또는 `SGIS_MCP_OUT`)에 저장됩니다.

## 키 없이 체험

```bash
python3 sgis_mcp_server.py --fixtures tests/fixtures
```

`tests/fixtures`의 **가짜 응답**(SGIS 문서의 호출결과 예제 + 테스트용 합성 값)으로 돕니다.
이 모드의 모든 결과와 지도에는 「가짜 응답 — 테스트용」이 찍힙니다. 실제 통계로 쓰지 마세요.

## 이렇게 물어보세요

- 「경남 창원시 의창구 읍면동별 65세 이상 인구 비율을 지도로 그리고, 가장 높은 동 세 곳을 알려 줘」
- 「대전 서구 청사로 189의 행정동과 그 동의 1인가구 수는?」
- 「경상남도 시군구별 산업용 기계·장비 임대업 사업체 수(최신 연도)」

AI는 `sgis_find_region`으로 코드를 찾고 → 통계 도구를 부르고 → 결과의 `citation.text`를 답 끝에 붙입니다.

## 근거를 남기는 법

`SGIS_MCP_LOG=/경로/calls.jsonl`을 주면 호출마다 `{도구, API, trId, 소요 ms, 성공 여부, 행 수}` 한 줄을 남깁니다
(인증키·토큰은 기록하지 않습니다). 라이브 검증 기록: [`docs/live-check.md`](docs/live-check.md).

## 개발

- 명세: [`SPEC.md`](SPEC.md) — 목적 · 숫자 성공조건 · Given/When/Then · 외부 사실(2026-09-24 실측)
- 테스트: `python3 -m pytest -q` (네트워크 0, 가짜 응답)
- 레이어: `domain ← application ← adapters ← infrastructure` (역방향 import는 `tests/test_layers.py`가 막음)

## 라이선스 · 데이터 출처

코드는 MIT. 통계 데이터의 저작권과 이용 조건은 **국가데이터처 통계지리정보서비스(SGIS)** 이용약관을 따릅니다.
이 프로젝트는 국가데이터처와 무관한 개인 오픈소스입니다.

---

**English (short)** — An MCP server that lets AI assistants (Claude, Codex, Gemini CLI) query Statistics Korea's SGIS
OpenAPI (population, households, housing, businesses, geocoding, administrative boundaries) and draw choropleth maps,
citing the SGIS transaction id with every number. Zero dependencies (Python 3.9+ stdlib).
