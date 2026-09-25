"""SgisService 유스케이스 — 가짜 포트(네트워크 0). UC-1~12."""
import pytest

from sgis_mcp.application.service import SgisService
from sgis_mcp.domain.errors import InvalidAdmCode, InvalidArgument
from tests.fakes import FakePort, MemorySink, default_routes, ok


def svc(extra=None):
    port = FakePort((extra or []) + default_routes())
    return SgisService(port, MemorySink()), port


def test_uc1_data_years_latest():
    s, _ = svc()
    out = s.data_years()
    assert out["latest"]["census"] == 2024 and out["latest"]["company"] == 2023 and out["latest"]["boundary"] == 2024
    assert out["citation"]["api_id"] == "API_9902"


def test_uc2_find_region_walks_three_levels():
    s, port = svc()
    out = s.find_region("경남 창원시 의창구 팔용동")
    assert out["method"] == "stage"
    assert out["candidates"][0]["adm_cd"] == "38111510"
    assert out["candidates"][0]["level"] == "eupmyeondong"
    assert out["candidates"][0]["full_name"] == "경상남도 창원시 의창구 팔용동"
    assert ("addr/stage.json", {"cd": "38111"}) in port.calls


def test_uc2_ambiguous_city_prefers_branch_where_dong_exists():
    s, _ = svc()
    out = s.find_region("경남 창원시 상남동")
    assert [c["adm_cd"] for c in out["candidates"]] == ["38112510"]


def test_uc2_sigungu_only():
    s, _ = svc()
    out = s.find_region("경상남도 진주시")
    assert [c["adm_cd"] for c in out["candidates"]] == ["38030"]
    assert out["candidates"][0]["level_ko"] == "시군구"


def test_uc2_stage_lists_are_cached():
    s, port = svc()
    s.find_region("경남 창원시 의창구")
    s.find_region("경남 진주시")
    assert sum(1 for p, q in port.calls if p == "addr/stage.json" and not q) == 1


def test_uc2_falls_back_to_geocode_without_sido():
    geo = ok("API_0707", {"totalcount": "1", "matching": "0", "resultdata": [
        {"sido_cd": "38", "sido_nm": "경상남도", "sgg_cd": "38111", "sgg_nm": "창원시 의창구", "adm_cd": "38111510",
         "adm_nm": "팔용동", "x": "128.6", "y": "35.2", "addr_type": "4"}]})
    s, _ = svc([("addr/geocodewgs84.json", {}, geo)])
    out = s.find_region("의창구 팔용동")
    assert out["method"] == "geocode"
    assert out["candidates"][0]["adm_cd"] == "38111510"


def test_uc3_population_summary_parses_and_cites():
    s, port = svc()
    out = s.population_summary("38111")
    assert out["year"] == 2024
    assert out["rows"][0]["tot_ppltn"] == 1000 and out["rows"][0]["imga_ppltn"] is None
    assert out["fields"]["tot_ppltn"] == "총인구"
    assert out["citation"]["survey"].startswith("인구주택총조사") and out["citation"]["year"] == 2024
    assert ("stats/population.json", {"year": 2024, "low_search": 1, "adm_cd": "38111"}) in port.calls


def test_uc3_rejects_bad_code_and_low_search():
    s, _ = svc()
    with pytest.raises(InvalidAdmCode):
        s.population_summary("창원")
    with pytest.raises(InvalidArgument):
        s.population_summary("38111", low_search=5)


def test_uc4_age_by_name_and_gender():
    s, port = svc()
    out = s.population_by_age("38111", age_type="65세이상", gender=2, year=2020)
    assert out["age_type"] == "24" and out["age_label"] == "65세이상" and out["gender_label"] == "여자"
    age_call = [q for pth, q in port.calls if pth == "stats/searchpopulation.json"][-1]
    assert age_call["age_type"] == "24" and age_call["gender"] == 2
    with pytest.raises(InvalidArgument):
        s.population_by_age("38111", gender=3)


def test_uc5_households_type_code():
    hh = ok("API_0305", [{"adm_cd": "38111510", "adm_nm": "팔용동", "household_cnt": "705",
                          "family_member_cnt": 1420, "avg_family_member_cnt": "2"}])
    s, port = svc([("stats/household.json", {}, hh)])
    out = s.households("38111", household_type="1인가구")
    assert out["rows"][0]["household_cnt"] == 705 and port.calls[-1][1]["household_type"] == "A0"


def test_uc6_houses():
    hs = ok("API_0306", [{"adm_cd": "38111", "adm_nm": "의창구", "house_cnt": 1}])
    s, port = svc([("stats/house.json", {}, hs)])
    out = s.houses("38", low_search=1, house_type="아파트")
    assert port.calls[-1][1]["house_type"] == "02" and out["rows"][0]["house_cnt"] == 1


def test_uc7_companies_default_year_and_exclusive_codes():
    cp = ok("API_0304", [{"adm_cd": "38111", "adm_nm": "의창구", "corp_cnt": "817", "tot_worker": "3588"}])
    s, port = svc([("stats/company.json", {}, cp)])
    out = s.companies("38", class_code="N763")
    assert out["year"] == 2023 and out["rows"][0]["tot_worker"] == 3588
    assert out["citation"]["survey"] == "전국사업체조사"
    with pytest.raises(InvalidArgument):
        s.companies("38", class_code="N763", theme_cd="CD1")


def test_uc8_industry_codes_class_deg_from_year():
    ic = ok("API_0303", [{"class_code": "N763", "class_nm": "산업용 기계 및 장비 임대업"}])
    s, port = svc([("stats/industrycode.json", {}, ic)])
    out = s.industry_codes(year=2023, class_code="N76")
    assert port.calls[-1][1] == {"class_deg": "10", "class_code": "N76"}
    assert out["codes"] == [{"class_code": "N763", "class_nm": "산업용 기계 및 장비 임대업"}]


def test_uc9_geocode_returns_wgs84_and_codes():
    geo = ok("API_0707", {"totalcount": "1", "matching": "0", "resultdata": [
        {"sido_nm": "대전광역시", "sgg_nm": "서구", "adm_nm": "둔산2동", "adm_cd": "25030600", "sgg_cd": "25030",
         "sido_cd": "25", "road_nm": "청사로", "road_nm_main_no": "189", "x": "127.38083451894656",
         "y": "36.36172224312449", "addr_type": "6", "leg_nm": "둔산동"}]})
    s, _ = svc([("addr/geocodewgs84.json", {}, geo)])
    out = s.geocode("대전 서구 청사로 189")
    r = out["results"][0]
    assert r["lon"] == pytest.approx(127.3808345) and r["lat"] == pytest.approx(36.3617222)
    assert r["adm_cd"] == "25030600" and "둔산2동" in r["address"]


def test_uc10_reverse_geocode_builds_adm_cd_and_checks_bounds():
    rg = ok("API_0708", [{"sgg_cd": "030", "emdong_cd": "570", "full_addr": "대전광역시 서구 탄방동",
                          "sido_nm": "대전광역시", "sgg_nm": "서구", "emdong_nm": "탄방동", "sido_cd": "25"}])
    s, _ = svc([("addr/rgeocodewgs84.json", {}, rg)])
    out = s.reverse_geocode(127.38, 36.36)
    assert out["results"][0]["adm_cd"] == "25030570" and out["results"][0]["full_addr"] == "대전광역시 서구 탄방동"
    with pytest.raises(InvalidArgument):
        s.reverse_geocode(36.36, 127.38)  # 경도·위도를 뒤집으면 막는다


def test_uc11_transform_coord_normalizes_epsg():
    tc = ok("API_0201", {"posX": 990391.6062050104, "posY": 1816238.1323095055})
    s, port = svc([("transformation/transcoord.json", {}, tc)])
    out = s.transform_coord(127.0, 36.0, src=4326, dst="EPSG:5179")
    assert port.calls[-1][1]["src"] == "EPSG:4326" and port.calls[-1][1]["dst"] == "EPSG:5179"
    assert out["x"] == pytest.approx(990391.606) and out["srs"] == "EPSG:5179"


def test_uc12_choropleth_age_share_writes_svg():
    s, port = svc()
    out = s.choropleth("38111", age_type="65세이상")
    assert out["svg_path"].endswith(".svg") and out["unit"] == "%"
    vals = {r["adm_cd"]: r["value"] for r in out["rows"]}
    assert vals["38111510"] == pytest.approx(25.0) and vals["38111520"] == pytest.approx(15.0)
    assert out["unmatched"]["boundary_without_stats"] == ["38111530"]
    svg = s.sink.files[out["svg_path"].split("/")[-1]]
    assert "65세이상 인구 비율" in svg and "trId" in svg
    assert len(out["citations"]) == 3  # 총인구 · 연령 인구 · 경계


def test_uc12_choropleth_metric_field():
    s, _ = svc()
    out = s.choropleth("38111", metric="avg_age")
    assert out["unit"] == "세" and out["label"] == "평균나이"
    with pytest.raises(InvalidArgument):
        s.choropleth("38111", metric="nope")



def test_uc2_citation_lists_stage_trids_walked():
    s, _ = svc()
    out = s.find_region("경남 창원시 의창구 팔용동")
    assert out["citation"]["tr_id"] == "t_API_0701, t_API_0701, t_API_0701"


def test_low_search_auto_zero_for_eupmyeondong_one_otherwise():
    s, port = svc()
    s.population_summary("38111510")
    assert port.calls[-1][1]["low_search"] == 0
    s.population_summary("38111")
    assert port.calls[-1][1]["low_search"] == 1
    s.population_summary("38111510", low_search=1)
    assert port.calls[-1][1]["low_search"] == 1


def test_uc4_share_pct_computed_by_server():
    s, port = svc()
    out = s.population_by_age("38111", age_type="65세이상")
    r = {row["adm_cd"]: row for row in out["rows"]}
    assert r["38111510"]["share_pct"] == 25.0 and r["38111510"]["tot_ppltn"] == 1000
    assert r["38111520"]["share_pct"] == 15.0
    assert len(out["citations"]) == 2 and "share_note" in out
    out2 = s.population_by_age("38111", age_type="65세이상", with_share=False)
    assert "share_pct" not in out2["rows"][0]


def test_uc2_legal_dong_name_resolves_via_geocode_under_stage_match():
    # 2026-09-25 라이브: SGIS 단계별 주소의 행정동은 「팔룡동」, 사람들은 법정동 이름 「팔용동」으로 묻는다.
    # 단계 탐색은 의창구(38111)에서 멈췄다 → 마지막 토큰이 동·읍·면으로 끝나면 지오코딩으로 그 아래 행정동을 찾는다.
    emd = ok("API_0701", [{"cd": "38111520", "addr_name": "팔룡동", "full_addr": "경상남도 창원시 의창구 팔룡동"},
                          {"cd": "38111530", "addr_name": "명곡동", "full_addr": "경상남도 창원시 의창구 명곡동"}])
    geo = ok("API_0707", {"totalcount": "1", "resultdata": [
        {"sido_cd": "38", "sido_nm": "경상남도", "sgg_cd": "38111", "sgg_nm": "창원시 의창구", "adm_cd": "38111520",
         "adm_nm": "팔용동", "leg_nm": "팔용동", "x": "128.62", "y": "35.24", "addr_type": "3"}]}, tr="g")
    s, port = svc([("addr/stage.json", {"cd": "38111"}, emd), ("addr/geocodewgs84.json", {}, geo)])
    out = s.find_region("경남 창원시 의창구 팔용동")
    top = out["candidates"][0]
    assert top["adm_cd"] == "38111520" and top["level"] == "eupmyeondong"
    assert top["full_name"] == "경상남도 창원시 의창구 팔룡동"  # 이름은 SGIS 행정동 목록 기준
    assert out["method"] == "stage+geocode" and "g_API_0707" in out["citation"]["tr_id"]


def test_uc2_no_geocode_when_stage_reaches_dong():
    s, port = svc()
    s.find_region("경남 창원시 의창구 팔용동")
    assert not any(p == "addr/geocodewgs84.json" for p, _ in port.calls)


def test_uc2_geocode_failure_keeps_stage_result():
    # 라이브: 지오코딩이 -1(「서버에서 처리 중 에러가 발생하였습니다.」)·-200을 줄 수 있다 → 단계 탐색 결과는 그대로 돌려준다
    from sgis_mcp.domain.errors import SgisApiError
    emd = ok("API_0701", [{"cd": "38111520", "addr_name": "팔룡동", "full_addr": "경상남도 창원시 의창구 팔룡동"}])
    s, port = svc([("addr/stage.json", {"cd": "38111"}, emd)])
    real = port.call

    def call(path, params):
        if path == "addr/geocodewgs84.json":
            raise SgisApiError(-1, "서버에서 처리 중 에러가 발생하였습니다.", "API_0707", "e")
        return real(path, params)

    port.call = call
    out = s.find_region("경남 창원시 의창구 팔용동")
    assert out["method"] == "stage" and out["candidates"][0]["adm_cd"] == "38111"
