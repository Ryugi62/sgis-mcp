"""테스트용 가짜 포트 — 네트워크 0."""
from sgis_mcp.application.ports import ApiResponse


class FakePort:
    """(경로, 파라미터 일부) → 응답 dict. 가장 구체적인(파라미터가 많이 맞는) 항목을 쓴다."""

    def __init__(self, routes):
        self.routes = routes  # list of (path, match_params:dict, data:dict)
        self.calls = []

    def call(self, path, params):
        clean = {k: v for k, v in params.items() if v is not None}
        self.calls.append((path, clean))
        best, best_n = None, -1
        for p, match, data in self.routes:
            if p != path:
                continue
            if all(str(clean.get(k)) == str(v) for k, v in match.items()) and len(match) > best_n:
                best, best_n = data, len(match)
        if best is None:
            raise AssertionError(f"route 없음: {path} {clean}")
        return ApiResponse(data=best, api_id=best.get("id"), tr_id=best.get("trId"))


class MemorySink:
    def __init__(self):
        self.files = {}

    def write_text(self, name, text):
        self.files[name] = text
        return "/mem/" + name


def ok(api_id, result, tr="t"):
    return {"id": api_id, "errCd": 0, "errMsg": "Success", "trId": f"{tr}_{api_id}", "result": result}


YEARS = ok("API_9902", {"lin_yr": "2024", "lcorp_yr": "2023", "laff_yr": "2020", "lboudary_yr": "2024",
                        "tin_yr": ["2015", "2020", "2024"], "tcorp_yr": ["2022", "2023"],
                        "tboudary_yr": ["2023", "2024"], "loa_yr": "2024"})
SIDOS = ok("API_0701", [{"cd": "11", "addr_name": "서울특별시", "full_addr": "서울특별시"},
                        {"cd": "38", "addr_name": "경상남도", "full_addr": "경상남도"}])
SGG38 = ok("API_0701", [{"cd": "38111", "addr_name": "창원시 의창구", "full_addr": "경상남도 창원시 의창구"},
                        {"cd": "38112", "addr_name": "창원시 성산구", "full_addr": "경상남도 창원시 성산구"},
                        {"cd": "38030", "addr_name": "진주시", "full_addr": "경상남도 진주시"}])
EMD38111 = ok("API_0701", [{"cd": "38111510", "addr_name": "팔용동", "full_addr": "경상남도 창원시 의창구 팔용동"},
                           {"cd": "38111520", "addr_name": "명곡동", "full_addr": "경상남도 창원시 의창구 명곡동"}])
EMD38112 = ok("API_0701", [{"cd": "38112510", "addr_name": "상남동", "full_addr": "경상남도 창원시 성산구 상남동"}])
SQ = lambda x0, y0: [[[x0, y0], [x0 + 100, y0], [x0 + 100, y0 + 100], [x0, y0 + 100], [x0, y0]]]
BOUNDARY = {"type": "FeatureCollection", "id": "API_0704", "errCd": 0, "errMsg": "Success", "trId": "b_API_0704",
            "features": [
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": SQ(0, 0)},
                 "properties": {"adm_cd": "38111510", "adm_nm": "경상남도 창원시 의창구 팔용동"}},
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": SQ(100, 0)},
                 "properties": {"adm_cd": "38111520", "adm_nm": "경상남도 창원시 의창구 명곡동"}},
                {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": SQ(0, 100)},
                 "properties": {"adm_cd": "38111530", "adm_nm": "경상남도 창원시 의창구 봉림동"}}]}
POP = ok("API_0301", [{"adm_cd": "38111510", "adm_nm": "팔용동", "tot_ppltn": "1000", "avg_age": "40.5", "imga_ppltn": "N/A"},
                      {"adm_cd": "38111520", "adm_nm": "명곡동", "tot_ppltn": "2000", "avg_age": "38.0", "imga_ppltn": "N/A"}])
POP65 = ok("API_0312", [{"adm_cd": "38111510", "adm_nm": "팔용동", "population": "250"},
                        {"adm_cd": "38111520", "adm_nm": "명곡동", "population": "300"}])


def default_routes():
    return [("year/data.json", {}, YEARS), ("addr/stage.json", {}, SIDOS), ("addr/stage.json", {"cd": "38"}, SGG38),
            ("addr/stage.json", {"cd": "38111"}, EMD38111), ("addr/stage.json", {"cd": "38112"}, EMD38112),
            ("boundary/hadmarea.geojson", {}, BOUNDARY), ("stats/population.json", {}, POP),
            ("stats/searchpopulation.json", {}, POP65)]
