"""통계행 파싱·코드표·출처 — UC-3~8 공통."""
import pytest

from sgis_mcp.domain.citation import Citation
from sgis_mcp.domain.errors import InvalidArgument
from sgis_mcp.domain.stats import (FIELD_LABELS, class_deg_for_year, parse_number, parse_rows, resolve_age_type,
                                   resolve_household_type)


def test_parse_number_variants():
    assert parse_number("148920") == 148920
    assert parse_number("39.2") == 39.2
    assert parse_number(452) == 452
    assert parse_number("N/A") is None
    assert parse_number("") is None
    assert parse_number(None) is None
    assert parse_number("null") is None


def test_parse_rows_doc_example():
    raw = [{"imga_ppltn": "N/A", "adm_cd": "11010", "tot_ppltn": "148920", "avg_age": "39.2", "adm_nm": "종로구"}]
    rows = parse_rows(raw, ["tot_ppltn", "avg_age", "imga_ppltn"])
    assert rows == [{"adm_cd": "11010", "adm_nm": "종로구", "tot_ppltn": 148920, "avg_age": 39.2, "imga_ppltn": None}]


def test_parse_rows_keeps_all_fields_when_none_given():
    rows = parse_rows([{"adm_cd": "1", "adm_nm": "x", "population": 3, "extra": "7"}])
    assert rows[0]["population"] == 3 and rows[0]["extra"] == 7


def test_field_labels_are_doc_wording():
    assert FIELD_LABELS["aged_child_idx"] == "노령화지수(일백명당 명)"
    assert FIELD_LABELS["tot_ppltn"] == "총인구"


@pytest.mark.parametrize("year,deg", [(2000, "8"), (2005, "8"), (2006, "9"), (2016, "9"), (2017, "10"),
                                      (2023, "10"), (2024, "11")])
def test_class_deg_for_year(year, deg):
    assert class_deg_for_year(year) == deg


def test_resolve_age_type_by_code_and_name():
    assert resolve_age_type("24") == "24"
    assert resolve_age_type("65세이상") == "24"
    assert resolve_age_type("65세 이상") == "24"
    assert resolve_age_type("0~4세") == "01"
    assert resolve_age_type(["14", "15세미만"]) == "14,22"
    with pytest.raises(InvalidArgument):
        resolve_age_type("99")


def test_resolve_household_type():
    assert resolve_household_type("1인가구") == "A0"
    assert resolve_household_type("a0") == "A0"
    assert resolve_household_type(["01", "02"]) == "01,02"
    with pytest.raises(InvalidArgument):
        resolve_household_type("Z9")


def test_citation_text_names_agency_survey_year_and_trid():
    c = Citation(survey="인구주택총조사", year=2024, api_id="API_0301", tr_id="abc_API_0301_1")
    t = c.text()
    assert "국가데이터처" in t and "SGIS" in t and "인구주택총조사" in t and "2024" in t and "abc_API_0301_1" in t
    d = c.to_dict()
    assert d["api_id"] == "API_0301" and d["fixture"] is False and d["text"] == t


def test_citation_fixture_flag_is_visible():
    c = Citation(survey="인구주택총조사", year=2024, api_id="API_0301", tr_id="t", fixture=True)
    assert "가짜 응답" in c.text() and c.to_dict()["fixture"] is True
