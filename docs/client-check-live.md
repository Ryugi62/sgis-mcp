# AI 클라이언트 연결 확인 — Claude Code CLI (실제 SGIS 호출)

> 2026-09-25 19:25 KST · `claude -p … --mcp-config`로 이 서버만 붙여(내장 도구·웹 끔) 한 번 물었다. 인증키로 실제 SGIS OpenAPI를 불렀다 — 9월 24일 시험용 응답판 기록은 [`client-check.md`](client-check.md), 12종 실호출은 [`live-check.md`](live-check.md).

## 질문

> 경남 창원시 의창구 팔용동의 총인구를 SGIS 도구로 조회하고, 의창구 읍면동별 65세 이상 인구 비율 지도를 만들어 줘. 값과 결과의 출처 문구(citation.text)를 그대로 붙여 한국어로 짧게 답해.

## AI가 부른 도구(서버 호출 기록 `SGIS_MCP_LOG` → `client-check-live-calls.jsonl`)

| # | 도구 | 서버 처리 ms |
|---|---|---|
| 1 | `sgis_find_region` | 1196.6 |
| 2 | `sgis_find_region` | 0.4 |
| 3 | `sgis_population_summary` | 242.5 |
| 4 | `sgis_choropleth` | 511.0 |

SGIS API 실제 호출 10회(인증 포함, 캐시 재사용 제외) · 대화 전체 14.6초 · AI 턴 5회 · 모델 claude-opus-5-5

SGIS 거래번호(trId): `Ojll_API_0101_1790331946960`, `L*QX_API_0701_1790331947060`, `ztva_API_0701_1790331947789`, `MNdM_API_0701_1790331947897`, `RVpU_API_0707_1790331948027`, `QWU2_API_9902_1790331950336`, `59ti_API_0301_1790331950455`, `zaNC_API_0301_1790331951079`, `Tu8a_API_0312_1790331951214`, `9Gxg_API_0704_1790331951368`

## AI의 답(원문)

**1. 팔룡동 총인구 (2024년 기준)**
- 창원시 의창구 팔룡동(adm_cd 38111520)의 총인구는 **25,854명**입니다. 요청하신 '팔용동'의 행정동 공식 이름은 '팔룡동'입니다.
- 출처: 국가데이터처 통계지리정보서비스(SGIS) OpenAPI · 인구주택총조사(총조사 주요지표) 2024년 기준 · API_0301 · trId 59ti_API_0301_1790331950455 (https://sgis.mods.go.kr)

**2. 의창구 읍면동별 65세 이상 인구 비율 지도 (2024년 기준)**
- 지도 파일: `~/dev/sgis-mcp/docs/img/sgis_38111_age_share_24_2024.svg`

| 읍면동 | 65세 이상 비율 |
|---|---|
| 대산면 | 35.44% |
| 동읍 | 26.33% |
| 봉림동 | 19.5% |
| 명곡동 | 18.25% |
| 의창동 | 16.34% |
| 북면 | 14.79% |
| 팔룡동 | 13.15% |

- 출처: 국가데이터처 통계지리정보서비스(SGIS) OpenAPI · 인구주택총조사(총조사 주요지표) 2024년 기준 · API_0301 · trId zaNC_API_0301_1790331951079 (https://sgis.mods.go.kr)
- 출처: 국가데이터처 통계지리정보서비스(SGIS) OpenAPI · 인구주택총조사 2024년 기준 · API_0312 · trId Tu8a_API_0312_1790331951214 (https://sgis.mods.go.kr)
- 출처: 국가데이터처 통계지리정보서비스(SGIS) OpenAPI · 행정구역경계 2024년 기준 · API_0704 · trId 9Gxg_API_0704_1790331951368 (https://sgis.mods.go.kr)
