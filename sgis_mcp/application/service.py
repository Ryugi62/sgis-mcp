"""유스케이스 — SGIS 도구 12개의 행동(SPEC §5). 포트만 알고 HTTP·JSON-RPC는 모른다."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ..domain.admcode import LEVEL_KO, AdmCode
from ..domain.choropleth import features_from_geojson, quantile_breaks, render_svg
from ..domain.citation import Citation
from ..domain.errors import InvalidAdmCode, InvalidArgument
from ..domain.region_match import Region, match_regions, tokenize
from ..domain.stats import (AGE_TYPES, FIELD_LABELS, HOUSE_TYPES, HOUSEHOLD_TYPES, SUMMARY_FIELDS, class_deg_for_year,
                            parse_number, parse_rows, resolve_age_type, resolve_house_type, resolve_household_type)
from .ports import ApiResponse, FileSink, SgisPort

GENDER = {0: "전체", 1: "남자", 2: "여자"}
SURVEY_CENSUS = "인구주택총조사"
SURVEY_COMPANY = "전국사업체조사"
UNITS = {"tot_ppltn": "명", "avg_age": "세", "ppltn_dnsty": "명/㎢", "aged_child_idx": "", "oldage_suprt_per": "",
         "juv_suprt_per": "", "tot_family": "가구", "avg_fmember_cnt": "명", "tot_house": "호", "corp_cnt": "개",
         "employee_cnt": "명"}


def _cite(r: ApiResponse, survey: str, year: Optional[int]) -> dict:
    return Citation(survey=survey, year=year, api_id=r.api_id, tr_id=r.tr_id, fixture=r.fixture).to_dict()


def _low(low_search, code=None) -> int:
    if low_search in (None, ""):  # 자동: 읍면동이면 그 지역만(아래는 집계구), 그 밖은 한 단계 아래
        return 0 if code is not None and code.level == "eupmyeondong" else 1
    try:
        v = int(low_search)
    except (TypeError, ValueError):
        raise InvalidArgument("low_search는 0(그 지역만)·1(한 단계 아래)·2(두 단계 아래)")
    if v not in (0, 1, 2):
        raise InvalidArgument("low_search는 0(그 지역만)·1(한 단계 아래)·2(두 단계 아래)")
    return v


def _epsg(v) -> str:
    s = str(v).strip().upper()
    if re.fullmatch(r"\d{4,6}", s):
        return "EPSG:" + s
    if re.fullmatch(r"EPSG:\d{4,6}", s):
        return s
    raise InvalidArgument(f"좌표계는 EPSG 코드(예: 4326 = WGS84 경위도, 5179 = UTM-K): {v!r}")


def _nn(v):
    return None if v in (None, "", "null", "NULL") else v


class SgisService:
    def __init__(self, port: SgisPort, sink: FileSink):
        self.port = port
        self.sink = sink
        self._stage_cache: Dict[Optional[str], List[Region]] = {}
        self._stage_tr: Dict[Optional[str], Optional[str]] = {}
        self._stage_fixture = False
        self._years: Optional[dict] = None

    # UC-1 ---------------------------------------------------------------
    def data_years(self) -> dict:
        r = self.port.call("year/data.json", {})
        res = r.result or {}

        def yr(k):
            v = parse_number(res.get(k))
            return v if isinstance(v, int) else None

        out = {"latest": {"census": yr("lin_yr"), "company": yr("lcorp_yr"), "agriculture": yr("laff_yr"),
                          "boundary": yr("lboudary_yr"), "small_area_boundary": yr("loa_yr")},
               "all": {"census": res.get("tin_yr"), "company": res.get("tcorp_yr"), "boundary": res.get("tboudary_yr"),
                       "farm": res.get("tag_yr"), "forestry": res.get("tfo_yr"), "fishery": res.get("tfi_yr")},
               "citation": _cite(r, "기준연도 정보", None)}
        self._years = out
        return out

    def _latest(self, kind: str) -> int:
        if self._years is None:
            self.data_years()
        v = self._years["latest"].get(kind) if self._years else None
        if not v:
            raise InvalidArgument(f"최신 {kind} 기준연도를 알 수 없습니다 — year를 직접 주세요")
        return v

    def _year(self, year, kind: str) -> int:
        if year in (None, ""):
            return self._latest(kind)
        try:
            return int(year)
        except (TypeError, ValueError):
            raise InvalidArgument(f"year는 4자리 연도: {year!r}")

    # UC-2 ---------------------------------------------------------------
    def _stage(self, cd: Optional[str]) -> List[Region]:
        if cd not in self._stage_cache:
            r = self.port.call("addr/stage.json", {"cd": cd})
            self._stage_tr[cd] = r.tr_id
            self._stage_fixture = self._stage_fixture or r.fixture
            self._stage_cache[cd] = [Region(str(x.get("cd")), str(x.get("addr_name") or ""),
                                            str(x.get("full_addr") or x.get("addr_name") or ""))
                                     for x in (r.result or [])]
        return self._stage_cache[cd]

    def _descend(self, parent: str, tokens: List[str]) -> List[Region]:
        hits = match_regions(" ".join(tokens), self._stage(parent))
        deeper: List[Region] = []
        shallow: List[Region] = []
        for region, consumed in hits[:6]:
            rest = [t for t in tokens if t not in consumed]
            if rest and len(region.code) == 5:
                d = self._descend(region.code, rest)
                if d:
                    deeper.extend(d)
                    continue
            shallow.append(region)
        return deeper or shallow

    @staticmethod
    def _cand(code: str, name: str, full: str) -> dict:
        level = AdmCode.parse(code).level
        return {"adm_cd": code, "name": name, "full_name": full, "level": level, "level_ko": LEVEL_KO[level]}

    def find_region(self, query: str, limit: int = 5) -> dict:
        q = (query or "").strip()
        if not q:
            raise InvalidArgument("query에 지명을 주세요(예: '경남 창원시 의창구 팔용동')")
        tokens = tokenize(q)
        results: List[Region] = []
        for sido, consumed in match_regions(q, self._stage(None))[:3]:
            rest = [t for t in tokens if t not in consumed]
            deeper = self._descend(sido.code, rest) if rest else []
            results.extend(deeper or [sido])
        if results:
            seen, cands = set(), []
            for r in results:
                if r.code not in seen:
                    seen.add(r.code)
                    cands.append(self._cand(r.code, r.name, r.full_name))
            walked = [None] + [c["adm_cd"][:n] for c in cands[:1] for n in (2, 5) if len(c["adm_cd"]) > n]
            trs = [self._stage_tr.get(cd) for cd in walked if self._stage_tr.get(cd)]
            cite = Citation("SGIS 단계별 주소", None, "API_0701", ", ".join(trs) or None,
                            self._stage_fixture).to_dict()
            return {"query": q, "method": "stage", "candidates": cands[:limit], "citation": cite}
        return self._find_by_geocode(q, limit)

    def _find_by_geocode(self, q: str, limit: int) -> dict:
        r = self.port.call("addr/geocodewgs84.json", {"address": q, "resultcount": max(1, min(50, int(limit)))})
        res = r.result or {}
        cands, seen = [], set()
        for x in res.get("resultdata") or []:
            code = _nn(x.get("adm_cd")) or _nn(x.get("sgg_cd")) or _nn(x.get("sido_cd"))
            try:
                AdmCode.parse(code)
            except InvalidAdmCode:
                continue
            if code in seen:
                continue
            seen.add(code)
            names = [n for n in (_nn(x.get("sido_nm")), _nn(x.get("sgg_nm")), _nn(x.get("adm_nm"))) if n]
            cands.append(self._cand(code, names[-1] if names else code, " ".join(names)))
        return {"query": q, "method": "geocode", "candidates": cands[:limit], "citation": _cite(r, "SGIS 지오코딩", None)}

    # UC-3~7 -------------------------------------------------------------
    def _stats(self, path: str, adm_cd, low_search, year: int, extra: Dict[str, Any], survey: str,
               fields: Optional[List[str]] = None) -> dict:
        code = AdmCode.parse_optional(adm_cd)
        params = {"year": year, "low_search": _low(low_search, code), "adm_cd": code.value if code else None}
        params.update({k: v for k, v in extra.items() if v is not None})
        r = self.port.call(path, params)
        rows = parse_rows(r.result, fields)
        keys = sorted({k for row in rows for k in row} - {"adm_cd", "adm_nm"})
        return {"year": year, "adm_cd": code.value if code else None, "low_search": params["low_search"],
                "rows": rows, "fields": {k: FIELD_LABELS.get(k, k) for k in keys}, "citation": _cite(r, survey, year)}

    def population_summary(self, adm_cd=None, low_search=None, year=None) -> dict:
        y = self._year(year, "census")
        return self._stats("stats/population.json", adm_cd, low_search, y, {}, SURVEY_CENSUS + "(총조사 주요지표)")

    def population_by_age(self, adm_cd=None, low_search=None, year=None, age_type=None, gender=0) -> dict:
        y = self._year(year, "census")
        g = int(gender) if str(gender).strip().isdigit() else -1
        if g not in GENDER:
            raise InvalidArgument("gender는 0(전체)·1(남자)·2(여자)")
        at = resolve_age_type(age_type)
        out = self._stats("stats/searchpopulation.json", adm_cd, low_search, y, {"age_type": at, "gender": g},
                          SURVEY_CENSUS)
        out.update({"age_type": at, "age_label": ", ".join(AGE_TYPES[c] for c in at.split(",")) if at else "전체",
                    "gender": g, "gender_label": GENDER[g]})
        return out

    def households(self, adm_cd=None, low_search=None, year=None, household_type=None) -> dict:
        y = self._year(year, "census")
        ht = resolve_household_type(household_type)
        out = self._stats("stats/household.json", adm_cd, low_search, y, {"household_type": ht}, SURVEY_CENSUS)
        out["household_type"] = ht
        out["household_label"] = ", ".join(HOUSEHOLD_TYPES[c] for c in ht.split(",")) if ht else "전체"
        return out

    def houses(self, adm_cd=None, low_search=None, year=None, house_type=None) -> dict:
        y = self._year(year, "census")
        ht = resolve_house_type(house_type)
        out = self._stats("stats/house.json", adm_cd, low_search, y, {"house_type": ht}, SURVEY_CENSUS)
        out["house_type"] = ht
        out["house_label"] = ", ".join(HOUSE_TYPES[c] for c in ht.split(",")) if ht else "전체"
        return out

    def companies(self, adm_cd=None, low_search=None, year=None, class_code=None, theme_cd=None) -> dict:
        if class_code and theme_cd:
            raise InvalidArgument("class_code(산업분류)와 theme_cd(테마)는 같이 쓸 수 없습니다(SGIS 문서)")
        y = self._year(year, "company")
        out = self._stats("stats/company.json", adm_cd, low_search, y,
                          {"class_code": class_code or None, "theme_cd": theme_cd or None}, SURVEY_COMPANY)
        out.update({"class_code": class_code or None, "theme_cd": theme_cd or None})
        return out

    # UC-8 ---------------------------------------------------------------
    def industry_codes(self, year=None, class_code=None) -> dict:
        y = self._year(year, "company")
        deg = class_deg_for_year(y)
        params = {"class_deg": deg}
        if class_code:
            params["class_code"] = str(class_code).strip()
        r = self.port.call("stats/industrycode.json", params)
        codes = [{"class_code": x.get("class_code"), "class_nm": x.get("class_nm")} for x in (r.result or [])]
        return {"year": y, "class_deg": deg, "parent": params.get("class_code"), "codes": codes,
                "citation": _cite(r, f"한국표준산업분류 {deg}차(전국사업체조사)", y)}

    # UC-9~11 ------------------------------------------------------------
    def geocode(self, address: str, limit: int = 5) -> dict:
        if not (address or "").strip():
            raise InvalidArgument("address에 주소를 주세요")
        r = self.port.call("addr/geocodewgs84.json", {"address": address.strip(),
                                                      "resultcount": max(1, min(50, int(limit)))})
        res = r.result or {}
        out = []
        for x in res.get("resultdata") or []:
            parts = [_nn(x.get(k)) for k in ("sido_nm", "sgg_nm", "adm_nm")]
            road = " ".join(p for p in (_nn(x.get("road_nm")), _nn(x.get("road_nm_main_no"))) if p)
            out.append({"address": " ".join(p for p in parts if p) + (f" ({road})" if road else ""),
                        "lon": parse_number(x.get("x")), "lat": parse_number(x.get("y")),
                        "sido_cd": _nn(x.get("sido_cd")), "sgg_cd": _nn(x.get("sgg_cd")), "adm_cd": _nn(x.get("adm_cd")),
                        "adm_nm": _nn(x.get("adm_nm")), "leg_nm": _nn(x.get("leg_nm")),
                        "addr_type": _nn(x.get("addr_type"))})
        return {"query": address.strip(), "totalcount": parse_number(res.get("totalcount")), "results": out,
                "coordinate_system": "WGS84(EPSG:4326)", "citation": _cite(r, "SGIS 지오코딩(WGS84)", None)}

    def reverse_geocode(self, lon, lat, addr_type: int = 20) -> dict:
        lon, lat = float(lon), float(lat)
        if not (124.0 <= lon <= 132.5 and 33.0 <= lat <= 39.0):
            raise InvalidArgument(f"대한민국 범위 밖 좌표입니다(경도 124~132.5, 위도 33~39): lon={lon}, lat={lat} — 뒤바뀌지 않았나요?")
        if int(addr_type) not in (10, 20, 21):
            raise InvalidArgument("addr_type은 10(도로명)·20(행정동)·21(행정동+지번)")
        r = self.port.call("addr/rgeocodewgs84.json", {"x_coor": lon, "y_coor": lat, "addr_type": int(addr_type)})
        out = []
        for x in r.result or []:
            parts = [_nn(x.get(k)) for k in ("sido_cd", "sgg_cd", "emdong_cd")]
            code = "".join(parts) if all(parts) else None
            out.append({"full_addr": _nn(x.get("full_addr")), "sido_nm": _nn(x.get("sido_nm")),
                        "sgg_nm": _nn(x.get("sgg_nm")), "emdong_nm": _nn(x.get("emdong_nm")), "adm_cd": code,
                        "road_nm": _nn(x.get("road_nm")), "addr_en": _nn(x.get("addr_en"))})
        return {"lon": lon, "lat": lat, "results": out, "citation": _cite(r, "SGIS 리버스 지오코딩(WGS84)", None)}

    def transform_coord(self, x, y, src=4326, dst=5179) -> dict:
        s, d = _epsg(src), _epsg(dst)
        r = self.port.call("transformation/transcoord.json", {"src": s, "dst": d, "posX": x, "posY": y})
        res = r.result or {}
        return {"input": {"x": x, "y": y, "srs": s}, "x": parse_number(res.get("posX")),
                "y": parse_number(res.get("posY")), "srs": res.get("toSrs") or d,
                "citation": _cite(r, "SGIS 좌표변환", None)}

    # UC-12 --------------------------------------------------------------
    def choropleth(self, parent_adm_cd=None, metric: str = "tot_ppltn", year=None, age_type=None,
                   title: Optional[str] = None, file_name: Optional[str] = None) -> dict:
        parent = AdmCode.parse_optional(parent_adm_cd)
        if parent is not None and parent.level == "eupmyeondong":
            raise InvalidArgument("단계구분도는 시도(2자리)·시군구(5자리) 아래 지역을 칠합니다")
        y = self._year(year, "census")
        citations = []
        summary = self.population_summary(parent.value if parent else None, 1, y)
        citations.append(summary["citation"])
        if age_type not in (None, "", []):
            at = resolve_age_type(age_type)
            age = self.population_by_age(parent.value if parent else None, 1, y, at, 0)
            citations.append(age["citation"])
            tot = {r["adm_cd"]: r.get("tot_ppltn") for r in summary["rows"]}
            values = {}
            for row in age["rows"]:
                t, p = tot.get(row["adm_cd"]), row.get("population")
                values[row["adm_cd"]] = round(p / t * 100, 2) if isinstance(p, (int, float)) and t else None
            label, unit, metric = f"{age['age_label']} 인구 비율", "%", f"age_share:{at}"
        else:
            if metric not in SUMMARY_FIELDS and not any(metric in r for r in summary["rows"]):
                raise InvalidArgument("metric은 총조사 주요지표 필드 중 하나: " +
                                      ", ".join(f"{k}={FIELD_LABELS[k]}" for k in SUMMARY_FIELDS))
            values = {r["adm_cd"]: (r.get(metric) if isinstance(r.get(metric), (int, float)) else None)
                      for r in summary["rows"]}
            label = re.sub(r"\(.*\)$", "", FIELD_LABELS.get(metric, metric))
            unit = UNITS.get(metric, "")
        latest_bnd = None
        try:
            latest_bnd = self._latest("boundary")
        except InvalidArgument:
            pass
        by = min(y, latest_bnd) if latest_bnd else y
        params = {"year": by, "low_search": 1}
        if parent is not None:
            params["adm_cd"] = parent.value
        b = self.port.call("boundary/hadmarea.geojson", params)
        citations.append(_cite(b, "행정구역경계", by))
        feats = features_from_geojson(b.data)
        names = {r["adm_cd"]: r.get("adm_nm") for r in summary["rows"]}
        mapped: Dict[str, Optional[float]] = {}
        for f in feats:
            mapped[f.adm_cd] = values.get(f.adm_cd)
        parent_name = " ".join((feats[0].adm_nm.split()[:-1] if feats else [])) or (parent.value if parent else "전국")
        head = title or f"{parent_name} {label} ({y}년)"
        tr = [c["tr_id"] for c in citations if c.get("tr_id")]
        source = (("[가짜 응답 — 테스트용] " if any(c["fixture"] for c in citations) else "") +
                  f"출처: 국가데이터처 SGIS OpenAPI · {SURVEY_CENSUS} {y} · 행정구역경계 {by} · trId " + ", ".join(tr))
        k = len(quantile_breaks(list(mapped.values()), 5))
        svg = render_svg(feats, mapped, title=head, unit=unit, source=source,
                         subtitle=f"{len(feats)}개 지역 · 분위 {k}단계 · 회색 = 자료 없음")
        fname = file_name or f"sgis_{parent.value if parent else 'kr'}_{re.sub(r'[^0-9A-Za-z_]+', '_', metric)}_{y}.svg"
        if not fname.endswith(".svg"):
            fname += ".svg"
        path = self.sink.write_text(fname, svg)
        rows = sorted(({"adm_cd": f.adm_cd, "adm_nm": names.get(f.adm_cd) or f.short_name, "value": mapped[f.adm_cd]}
                       for f in feats), key=lambda r: (r["value"] is None, -(r["value"] or 0)))
        return {"svg_path": path, "title": head, "label": label, "unit": unit, "metric": metric, "year": y,
                "boundary_year": by, "breaks": quantile_breaks(list(mapped.values()), 5), "rows": rows,
                "unmatched": {"boundary_without_stats": [f.adm_cd for f in feats if values.get(f.adm_cd) is None],
                              "stats_without_boundary": sorted(set(values) - {f.adm_cd for f in feats})},
                "citations": citations}
