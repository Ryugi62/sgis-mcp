# SPEC — sgis-mcp (SGIS OpenAPI를 생성형 AI 도구로 여는 MCP 서버)

## 0. 목적 (한 문단)
생성형 AI(Claude·Codex·Gemini CLI 등 MCP 클라이언트)가 한국의 인구·가구·주택·사업체 수치나 행정구역을 말할 때
**기억이 아니라 국가데이터처 SGIS OpenAPI 원값을 인용**하게 한다. 지명 한 줄(「창원시 의창구」)을 행정구역코드로 바꾸고,
통계를 조회하고, 읍면동 단계구분도(SVG)까지 한 번의 대화 안에서 끝낸다. 설치 0 — 파이썬 3.9+ 표준 라이브러리만.

## 1. 성공 조건 (숫자)
| # | 조건 | 측정 |
|---|---|---|
| S1 | 도구 12개, 전부 SGIS 개발지원센터 문서화 API에 대응 | `tools/list` = 12 · §6 대응표 |
| S2 | 자연어 지명 → 행정구역코드(시도·시군구·읍면동) | 가짜 응답 기반 테스트 ≥ 8건 |
| S3 | 통계를 돌려주는 모든 도구 응답에 출처(기관·조사·기준연도·API id·trId) 100% | 테스트 |
| S4 | 인증 만료(-401) → 재인증 1회 후 재시도, 두 번째도 실패면 도구 오류 | 계약 테스트 |
| S5 | 단계구분도 SVG: 경계(UTM-K) + 값 → 5분위 채색·범례·출처 줄, 외부 라이브러리 0 | 테스트 + 라이브 1회 |
| S6 | 테스트 ≥ 40, 네트워크 0, 레이어 역방향 import 0 | `pytest -q` · `tests/test_layers.py` |
| S7 | 라이브 검증: 인증키로 12도구 실호출 → `docs/live-check.md`(trId 목록) | `scripts/live_smoke.py` |
| S8 | initialize 응답 < 1초(콜드 스타트) | 부팅 테스트 |
| S9 | SGIS 부하 최소화: 같은 요청은 다시 보내지 않는다(세션 캐시 256건) · 토큰·주소 목록 재사용 | 계약 테스트 |

## 2. 비목표
지도 API(JavaScript) 래핑 · 웹 UI · 상용키 전환 절차 · 통계 해석/예측 · SGIS 비공개(내부) 엔드포인트 사용.

## 3. 유비쿼터스 언어 (코드 이름과 1:1)
| 용어 | 코드 | 뜻 |
|---|---|---|
| 행정구역코드 | `AdmCode` | 시도 2자리 · 시군구 5자리 · 읍면동 7/8자리(문서 구판 7, 신판 8) |
| 지역 | `Region` | 코드 + 이름 + 단계(`sido`/`sigungu`/`eupmyeondong`) |
| 기준연도 | `year` | 조사 기준연도. 생략하면 `year/data.json`의 최신 연도 |
| 하위 단계 | `low_search` | 0 = 그 지역만 · 1 = 한 단계 아래 · 2 = 두 단계 아래. 비우면 자동(읍면동 코드 → 0, 그 밖 → 1; 읍면동 아래는 집계구라 이름이 없다) |
| 통계행 | `StatRow` | 한 지역의 값 묶음. 「N/A」는 `None` |
| 출처 | `Citation` | 기관 · 조사명 · 기준연도 · API id · trId(SGIS 거래번호) |
| 거래번호 | `tr_id` | SGIS 응답의 `trId` — 호출을 SGIS 쪽 기록과 대조할 수 있는 키 |
| 인증 토큰 | `AccessToken` | `auth/authentication.json`이 준 `accessToken` + 만료시각 |
| 단계구분도 | `Choropleth` | 경계 다각형을 값의 분위로 칠한 지도(SVG) |

## 4. 모델
- `AdmCode.parse(str) -> AdmCode` (숫자·길이 2/5/7/8 아니면 `InvalidAdmCode`) · `.level`
- `match_regions(query, candidates) -> list[Region]` — 공백·약칭(서울·경남 …) 정규화 후 토큰 포함 점수
- `parse_rows(result, fields) -> list[StatRow]` — 숫자 문자열 → int/float, 「N/A」 → None
- `class_deg_for_year(year)` — 산업분류 차수(≤2005:8 · ≤2016:9 · ≤2023:10 · 그 뒤 11, 문서 신판)
- `quantile_breaks(values, k=5)` · `render_choropleth(features, values, title, citation) -> svg`

## 5. 유스케이스와 수용 기준 (Given / When / Then)
- **UC-1 기준연도** `sgis_data_years` — G 가짜 `year/data.json` W 호출 T 최신 인구·사업체·경계 연도와 전체 목록.
- **UC-2 지역 찾기** `sgis_find_region` — G 시도·시군구·읍면동 단계 목록 W 「경남 창원시 의창구 팔용동」 T 8자리 코드 1건이 1순위. 시도를 못 찾으면 지오코딩으로 대체(how=geocode).
- **UC-3 총조사 주요지표** `sgis_population_summary` — T 총인구·평균나이·인구밀도·노령화지수 … 숫자형 + 출처.
- **UC-4 연령·성별 인구** `sgis_population_by_age` — `age_type`(코드 01~41 또는 「65세이상」 같은 이름) · `gender` → 인구수 + 출처. 비율(`share_pct` = 인구 ÷ 같은 지역 총인구 × 100)은 서버가 계산해 붙인다(AI 암산 오류 방지).
- **UC-5 가구** `sgis_households` — `household_type`(A0 = 1인가구 …).
- **UC-6 주택** `sgis_houses` — `house_type`(02 = 아파트 …).
- **UC-7 사업체** `sgis_companies` — `class_code`(산업분류) 또는 `theme_cd`, 둘 다 주면 오류(문서 「같이 사용할 수 없음」).
- **UC-8 산업분류** `sgis_industry_codes` — `year`로 차수 자동, `class_code`로 하위 목록.
- **UC-9 지오코딩** `sgis_geocode` — 주소 → WGS84 좌표 + 행정동 코드.
- **UC-10 리버스 지오코딩** `sgis_reverse_geocode` — WGS84 좌표 → 주소·코드.
- **UC-11 좌표변환** `sgis_transform_coord` — EPSG 코드 간 변환(예: 4326 → 5179).
- **UC-12 단계구분도** `sgis_choropleth` — G 상위 지역 코드 + 지표(총조사 주요지표 필드 또는 연령 비율) W 호출 T SVG 파일 경로 · 5분위 경계 · 지역별 값 표 · 경계와 통계의 코드 불일치 수 · 출처.
- **AC-클라이언트** 실제 MCP 클라이언트(Claude Code CLI)가 도구를 찾아 부르고 citation을 답에 옮긴다 — `docs/client-check.md`(가짜 응답 모드, 2026-09-24).
- **AC-공통** 통계를 돌려주는 모든 도구 결과에 `citation` 키. `-401`이면 재인증 1회. 인증키가 없으면 첫 호출에서 「SGIS_CONSUMER_KEY/SECRET 설정」 안내 오류(서버는 뜬다).

## 6. 외부 사실 (2026-09-24 curl 실측 — 바뀌면 여기부터 고친다)
- 기본 주소 `https://sgisapi.mods.go.kr/OpenAPI3` · 구 주소 `sgisapi.kostat.go.kr`는 같은 경로로 **302** 전환.
- 인증 없이 부르면 HTTP 200 + `{"errCd":-401,"errMsg":"인증 정보가 존재하지 않습니다","id":"API_0301","trId":"…"}`.
- 필수 파라미터가 빠지면 HTML `필수 파라미터 누락`(JSON 아님).
- 개발지원센터 문서: 무료 · 일일 50,000회 이하 · 테스트키 「신청즉시 발급」 15일(연장 가능) · 상용키는 승인.
- 대응표:

| 도구 | SGIS API | 문서 id |
|---|---|---|
| sgis_data_years | `year/data.json` | API_1501 |
| sgis_find_region | `addr/stage.json` (+ `addr/geocodewgs84.json`) | API_0701 |
| sgis_population_summary | `stats/population.json` | API_0301 |
| sgis_population_by_age | `stats/searchpopulation.json` | API_0302 |
| sgis_households | `stats/household.json` | API_0305 |
| sgis_houses | `stats/house.json` | API_0306 |
| sgis_companies | `stats/company.json` | API_0304 |
| sgis_industry_codes | `stats/industrycode.json` | API_0303 |
| sgis_geocode | `addr/geocodewgs84.json` | API_0707 |
| sgis_reverse_geocode | `addr/rgeocodewgs84.json` | API_0708 |
| sgis_transform_coord | `transformation/transcoord.json` | API_0201 |
| sgis_choropleth | `boundary/hadmarea.geojson` + `stats/population.json` (+ `searchpopulation`) | API_0704 |

- 코드표(개발지원센터 dataCode 팝업): 연령 01~41(24 = 65세이상 · 22 = 15세미만 · 23 = 15~64세) · 세대유형 A0 = 1인가구 · 주택유형 01 단독 · 02 아파트 · 좌표계 WGS84 = EPSG:4326 · UTM-K = EPSG:5179.
- **가정(라이브 검증 대상)**: `errCd -100`은 「결과 없음」으로 빈 목록 처리 · `accessTimeout`이 1e12 이상이면 밀리초.

## 7. 레이어 (역방향 import 금지)
`sgis_mcp/domain` ← `sgis_mcp/application` ← `sgis_mcp/adapters` ← `sgis_mcp/infrastructure`
- domain: 순수 함수·값 객체(표준 라이브러리 수학·문자열만)
- application: 포트(`SgisPort`, `FileSink`)와 유스케이스(`SgisService`)
- adapters: SGIS HTTP 게이트웨이(토큰·오류 매핑, `Transport` 포트 사용) · MCP stdio(JSON-RPC 2.0)
- infrastructure: urllib 전송 · 가짜 응답 전송 · 설정 · 호출 기록(JSONL) · 조립(main)

## 8. 보안·운영
- 인증키는 환경변수 또는 `--env-file`(KEY=VALUE)로만. 응답·로그에 `accessToken`·보안 Key를 쓰지 않는다.
- `SGIS_MCP_LOG=<경로>`면 호출마다 `{ts, tool, api, trId, ms, ok, rows}` 한 줄(JSONL) — 활용 성과의 근거자료.
- 가짜 응답 모드(`SGIS_MCP_FIXTURES=<폴더>`)는 결과의 `citation.fixture = true`로 표시한다(실데이터와 혼동 금지).

## 9. 정확도 실험 (효과 측정 — 인증키 필요)
- **UC-B** `bench/run_bench.py` — G 시도 코드순 앞 N개 시도마다 코드 가운데 시군구 1곳(총인구 · 65세 이상 비율 = 2N문항, 정답은 SGIS 원값)
  W 같은 질문을 ①AI 단독(`claude -p`, 내장 도구·웹 끔) ②AI + 이 서버로 묻는다 T 조건별 원값 일치 수 · 오차 중앙값 · 출처 표기 수.
- 일치 기준(실행 전 고정): 인구 상대오차 ≤ 0.5% · 비율 절대오차 ≤ 0.1%p. 채점은 `bench/scoring.py`(순수 함수, 테스트).
- 결과는 `bench/out/`(정답 trId 포함). 숫자는 실행 결과만 인용한다.
