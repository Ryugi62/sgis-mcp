"""MCP 서버(표준 입출력, 줄 단위 JSON-RPC 2.0) — SGIS 도구 12개(SPEC §5·§6).

생성형 AI가 한국 공간통계를 말할 때 SGIS OpenAPI 원값과 출처(trId)를 그대로 인용하게 하는 연결부.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, IO, Optional

from .. import __version__
from ..application.service import SgisService
from ..domain.errors import SgisError
from ..domain.stats import AGE_TYPES, FIELD_LABELS, HOUSE_TYPES, HOUSEHOLD_TYPES, SUMMARY_FIELDS

SUPPORTED = ["2025-06-18", "2025-03-26", "2024-11-05"]
SERVER_INFO = {"name": "sgis-mcp", "title": "SGIS MCP — 국가데이터처 통계지리정보서비스 OpenAPI", "version": __version__}
INSTRUCTIONS = (
    "한국의 인구·가구·주택·사업체 수치, 행정구역 코드·경계, 주소 좌표를 말할 때는 기억으로 답하지 말고 SGIS 도구로 조회해 "
    "결과 값을 그대로 인용하세요. 지명은 먼저 sgis_find_region으로 행정구역코드(adm_cd)를 찾고, 통계 도구에 그 코드를 넘기세요. "
    "답 끝에 결과의 citation.text(국가데이터처 SGIS · 조사명 · 기준연도 · trId)를 붙이세요. 지도가 필요하면 sgis_choropleth.")

_ADM = {"type": "string", "description": "행정구역코드: 시도 2자리 · 시군구 5자리 · 읍면동 7/8자리. 비우면 전국(시도 목록). "
                                          "모르면 sgis_find_region으로 찾을 것"}
_LOW = {"type": "integer", "enum": [0, 1, 2], "default": 1,
        "description": "0 = 그 지역만 · 1 = 한 단계 아래 지역들(기본) · 2 = 두 단계 아래"}
_YEAR = {"type": "integer", "description": "기준연도(4자리). 비우면 SGIS가 알려 주는 최신 연도"}
_CODES = lambda table: "; ".join(f"{k}={v}" for k, v in table.items())

TOOLS = [
    {"name": "sgis_find_region",
     "description": "지명(예: '경남 창원시 의창구 팔용동', '서울 종로구')을 SGIS 행정구역코드(adm_cd)로 바꾼다. "
                    "시도→시군구→읍면동 단계 목록(addr/stage)을 따라가고, 시도가 없으면 지오코딩으로 찾는다. "
                    "Resolve a Korean place name to SGIS administrative codes.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "지명. 시도부터 쓰면 정확하다(경남·서울 같은 약칭 가능)"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5}}, "required": ["query"]}},
    {"name": "sgis_data_years",
     "description": "SGIS가 제공하는 최신·전체 기준연도(인구주택총조사·전국사업체조사·농림어업총조사·경계)를 알려 준다.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "sgis_population_summary",
     "description": "인구주택총조사 주요지표: " + ", ".join(FIELD_LABELS[k] for k in SUMMARY_FIELDS) +
                    " 등. 지역과 그 하위 지역별로 돌려준다. Census key indicators by region.",
     "inputSchema": {"type": "object", "properties": {"adm_cd": _ADM, "low_search": _LOW, "year": _YEAR}}},
    {"name": "sgis_population_by_age",
     "description": "연령·성별 조건 인구수(인구주택총조사). 예: 65세 이상 여성 인구. age_type 코드: " + _CODES(AGE_TYPES),
     "inputSchema": {"type": "object", "properties": {
         "adm_cd": _ADM, "low_search": _LOW, "year": _YEAR,
         "age_type": {"description": "연령 코드(예: '24') 또는 이름(예: '65세이상'), 여러 개면 배열",
                      "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
         "gender": {"type": "integer", "enum": [0, 1, 2], "default": 0, "description": "0 전체 · 1 남자 · 2 여자"}}}},
    {"name": "sgis_households",
     "description": "가구수·가구원수(인구주택총조사). household_type: " + _CODES(HOUSEHOLD_TYPES),
     "inputSchema": {"type": "object", "properties": {
         "adm_cd": _ADM, "low_search": _LOW, "year": _YEAR,
         "household_type": {"description": "세대구성 코드 또는 이름(예: '1인가구'), 여러 개면 배열",
                            "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}}}},
    {"name": "sgis_houses",
     "description": "주택수(인구주택총조사). house_type: " + _CODES(HOUSE_TYPES),
     "inputSchema": {"type": "object", "properties": {
         "adm_cd": _ADM, "low_search": _LOW, "year": _YEAR,
         "house_type": {"description": "주택유형 코드 또는 이름(예: '아파트')",
                        "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}}}},
    {"name": "sgis_companies",
     "description": "사업체수·종사자수(전국사업체조사). 업종은 class_code(sgis_industry_codes로 찾기) 또는 theme_cd 중 하나만.",
     "inputSchema": {"type": "object", "properties": {
         "adm_cd": _ADM, "low_search": _LOW, "year": _YEAR,
         "class_code": {"type": "string", "description": "한국표준산업분류 코드(예: 'N763')"},
         "theme_cd": {"type": "string", "description": "SGIS 테마코드"}}}},
    {"name": "sgis_industry_codes",
     "description": "SGIS 산업분류 코드 목록. year로 분류 차수(8·9·10·11차)를 자동 선택, class_code를 주면 그 하위 목록.",
     "inputSchema": {"type": "object", "properties": {
         "year": _YEAR, "class_code": {"type": "string", "description": "상위 코드(비우면 대분류)"}}}},
    {"name": "sgis_geocode",
     "description": "주소 → WGS84 경위도 + 행정동 코드(SGIS 지오코딩). Geocode a Korean address.",
     "inputSchema": {"type": "object", "properties": {
         "address": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 5}},
         "required": ["address"]}},
    {"name": "sgis_reverse_geocode",
     "description": "WGS84 경위도 → 주소·행정동 코드(SGIS 리버스 지오코딩). lon=경도(124~132), lat=위도(33~39).",
     "inputSchema": {"type": "object", "properties": {
         "lon": {"type": "number"}, "lat": {"type": "number"},
         "addr_type": {"type": "integer", "enum": [10, 20, 21], "default": 20,
                       "description": "10 도로명 · 20 행정동 · 21 행정동+지번"}}, "required": ["lon", "lat"]}},
    {"name": "sgis_transform_coord",
     "description": "좌표계 변환(SGIS). 예: WGS84 경위도(4326) → UTM-K(5179). src·dst는 EPSG 숫자.",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "number"}, "y": {"type": "number"},
         "src": {"type": ["integer", "string"], "default": 4326}, "dst": {"type": ["integer", "string"], "default": 5179}},
         "required": ["x", "y"]}},
    {"name": "sgis_choropleth",
     "description": "단계구분도(SVG 파일)를 만든다: 상위 지역(시도·시군구) 아래 지역들을 지표 값의 5분위로 칠하고 범례·출처(trId)를 넣는다. "
                    "metric = 총조사 주요지표 필드, 또는 age_type을 주면 그 연령 인구 비율(%). 결과에 파일 경로·지역별 값 표.",
     "inputSchema": {"type": "object", "properties": {
         "parent_adm_cd": {"type": "string", "description": "상위 지역 코드(시도 2 · 시군구 5). 비우면 전국 시도"},
         "metric": {"type": "string", "default": "tot_ppltn", "enum": SUMMARY_FIELDS,
                    "description": "; ".join(f"{k}={FIELD_LABELS[k]}" for k in SUMMARY_FIELDS)},
         "age_type": {"description": "주면 metric 대신 이 연령 인구 비율(%)을 칠한다(예: '65세이상')",
                      "anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
         "year": _YEAR, "title": {"type": "string"}, "file_name": {"type": "string"}}}},
]


class McpServer:
    def __init__(self, service: SgisService, on_tool: Optional[Callable[[dict], None]] = None):
        self.service = service
        self.on_tool = on_tool
        self.dispatch: Dict[str, Callable[[dict], Any]] = {
            "sgis_find_region": lambda a: service.find_region(a.get("query", ""), int(a.get("limit", 5) or 5)),
            "sgis_data_years": lambda a: service.data_years(),
            "sgis_population_summary": lambda a: service.population_summary(a.get("adm_cd"), a.get("low_search", 1), a.get("year")),
            "sgis_population_by_age": lambda a: service.population_by_age(a.get("adm_cd"), a.get("low_search", 1), a.get("year"),
                                                                          a.get("age_type"), a.get("gender", 0)),
            "sgis_households": lambda a: service.households(a.get("adm_cd"), a.get("low_search", 1), a.get("year"),
                                                            a.get("household_type")),
            "sgis_houses": lambda a: service.houses(a.get("adm_cd"), a.get("low_search", 1), a.get("year"), a.get("house_type")),
            "sgis_companies": lambda a: service.companies(a.get("adm_cd"), a.get("low_search", 1), a.get("year"),
                                                          a.get("class_code"), a.get("theme_cd")),
            "sgis_industry_codes": lambda a: service.industry_codes(a.get("year"), a.get("class_code")),
            "sgis_geocode": lambda a: service.geocode(a.get("address", ""), int(a.get("limit", 5) or 5)),
            "sgis_reverse_geocode": lambda a: service.reverse_geocode(a.get("lon"), a.get("lat"), a.get("addr_type", 20)),
            "sgis_transform_coord": lambda a: service.transform_coord(a.get("x"), a.get("y"), a.get("src", 4326),
                                                                      a.get("dst", 5179)),
            "sgis_choropleth": lambda a: service.choropleth(a.get("parent_adm_cd"), a.get("metric") or "tot_ppltn",
                                                            a.get("year"), a.get("age_type"), a.get("title"),
                                                            a.get("file_name")),
        }

    def handle(self, msg: dict) -> Optional[dict]:
        mid = msg.get("id")
        method = msg.get("method")
        if mid is None:
            return None  # 알림(notifications/initialized 등)에는 응답하지 않는다
        if method == "initialize":
            want = (msg.get("params") or {}).get("protocolVersion")
            result = {"protocolVersion": want if want in SUPPORTED else SUPPORTED[0],
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": SERVER_INFO, "instructions": INSTRUCTIONS}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            p = msg.get("params") or {}
            result = self.call(p.get("name"), p.get("arguments") or {})
        else:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def call(self, name: str, args: dict) -> dict:
        fn = self.dispatch.get(name)
        if fn is None:
            return self._err(f"알 수 없는 도구: {name}")
        t0 = time.perf_counter()
        ok = False
        try:
            out = fn(args)
            ok = True
            return self._ok(out)
        except SgisError as e:
            return self._err(str(e))
        except (TypeError, ValueError) as e:
            return self._err(f"입력값 오류: {e}")
        finally:
            if self.on_tool:
                self.on_tool({"kind": "tool", "tool": name, "ms": round((time.perf_counter() - t0) * 1000, 1), "ok": ok})

    @staticmethod
    def _ok(obj: Any) -> dict:
        return {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False)}], "isError": False}

    @staticmethod
    def _err(text: str) -> dict:
        return {"content": [{"type": "text", "text": text}], "isError": True}


def serve(stdin: IO[str], stdout: IO[str], server: McpServer) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            out = server.handle(msg) if isinstance(msg, dict) else {
                "jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
        if out is not None:
            stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            stdout.flush()
