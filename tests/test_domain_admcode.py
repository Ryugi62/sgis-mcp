"""AdmCode — 행정구역코드 값 객체(SPEC §3·§4)."""
import pytest

from sgis_mcp.domain.admcode import AdmCode
from sgis_mcp.domain.errors import InvalidAdmCode


@pytest.mark.parametrize("raw,level", [("11", "sido"), ("38111", "sigungu"), ("1104055", "eupmyeondong"),
                                       ("25030600", "eupmyeondong")])
def test_levels_by_length(raw, level):
    assert AdmCode.parse(raw).level == level


def test_strips_spaces_and_accepts_int():
    assert AdmCode.parse(" 38111 ").value == "38111"
    assert AdmCode.parse(11).value == "11"


@pytest.mark.parametrize("raw", ["", "1", "123", "abcde", "381111111", "38-11"])
def test_rejects_bad_codes(raw):
    with pytest.raises(InvalidAdmCode):
        AdmCode.parse(raw)


def test_parent_chain():
    assert AdmCode.parse("25030600").parent().value == "25030"
    assert AdmCode.parse("1104055").parent().value == "11040"
    assert AdmCode.parse("38111").parent().value == "38"
    assert AdmCode.parse("38").parent() is None


def test_optional_parse_none_means_nationwide():
    assert AdmCode.parse_optional(None) is None
    assert AdmCode.parse_optional("") is None
    assert AdmCode.parse_optional("38").value == "38"
