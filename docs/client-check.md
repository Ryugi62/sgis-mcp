# AI 클라이언트 연결 확인 — Claude Code CLI (가짜 응답 모드)

> 2026-09-24 13:54 KST · `claude -p … --mcp-config` 로 이 서버를 붙여 한 번 물었다. **데이터는 `tests/fixtures` 가짜 응답**이라 숫자는 실제 통계가 아니다 —
> 이 기록이 보여 주는 건 「AI가 도구를 찾아 순서대로 부르고, 출처(citation)를 답에 옮겨 적는다」는 연결 동작뿐이다. 실제 SGIS 호출 기록은 [`live-check.md`](live-check.md).

## 질문

> 경남 창원시 의창구 다동의 총인구를 SGIS 도구로 조회하고, 의창구 읍면동별 65세 이상 인구 비율 지도를 만들어 줘. 값과 결과의 출처 문구(citation.text)를 그대로 붙여 한국어로 짧게 답해.

## AI가 부른 도구(서버 호출 기록 `SGIS_MCP_LOG`)

| # | 도구 | 서버 처리 ms |
|---|---|---|
| 1 | `sgis_find_region` | 1.7 |
| 2 | `sgis_find_region` | 0.2 |
| 3 | `sgis_population_summary` | 0.9 |
| 4 | `sgis_choropleth` | 1.8 |

대화 전체 12.8초 · AI 턴 6회

## AI의 답(원문)

⚠️ SGIS 도구가 **테스트용 가짜 응답(fixture)**을 돌려줬습니다. 아래 수치는 실제 통계가 아닙니다.

**다동 총인구: 3,000명** (2024년 기준, adm_cd 38111530)

**의창구 읍면동별 65세 이상 인구 비율 지도:** `maps/sgis_38111_age_share_24_2024.svg`

| 읍면동 | 65세 이상 비율 |
|---|---|
| 다동 | 30.0% |
| 나동 | 15.0% |
| 가동 | 10.0% |
| 라동 | 10.0% |

출처:
- [가짜 응답 — 테스트용, 실제 통계 아님] 출처: 국가데이터처 통계지리정보서비스(SGIS) OpenAPI · 인구주택총조사(총조사 주요지표) 2024년 기준 · API_0301 · trId fx_API_0301 (https://sgis.mods.go.kr)
- [가짜 응답 — 테스트용, 실제 통계 아님] 출처: 국가데이터처 통계지리정보서비스(SGIS) OpenAPI · 인구주택총조사 2024년 기준 · API_0302 · trId fx_API_0302 (https://sgis.mods.go.kr)
- [가짜 응답 — 테스트용, 실제 통계 아님] 출처: 국가데이터처 통계지리정보서비스(SGIS) OpenAPI · 행정구역경계 2024년 기준 · API_0704 · trId fx_API_0704 (https://sgis.mods.go.kr)

실제 값이 필요하면 SGIS 서버를 테스트 모드가 아닌 실제 API 키로 설정한 뒤 다시 조회해야 합니다.
