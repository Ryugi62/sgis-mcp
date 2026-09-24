"""지명 → 지역 후보 매칭(순수 함수) — UC-2."""
from sgis_mcp.domain.region_match import Region, match_regions, sido_short, tokenize

SIDOS = [Region("11", "서울특별시", "서울특별시"), Region("21", "부산광역시", "부산광역시"),
         Region("29", "세종특별자치시", "세종특별자치시"), Region("32", "강원특별자치도", "강원특별자치도"),
         Region("35", "전북특별자치도", "전북특별자치도"), Region("37", "경상북도", "경상북도"),
         Region("38", "경상남도", "경상남도"), Region("39", "제주특별자치도", "제주특별자치도")]
SGGS = [Region("38111", "창원시 의창구", "경상남도 창원시 의창구"), Region("38112", "창원시 성산구", "경상남도 창원시 성산구"),
        Region("38113", "창원시 마산합포구", "경상남도 창원시 마산합포구"), Region("38030", "진주시", "경상남도 진주시")]


def test_sido_short_forms():
    assert sido_short("경상남도") == "경남"
    assert sido_short("충청북도") == "충북"
    assert sido_short("전라남도") == "전남"
    assert sido_short("서울특별시") == "서울"
    assert sido_short("강원특별자치도") == "강원"
    assert sido_short("세종특별자치시") == "세종"
    assert sido_short("경기도") == "경기"


def test_tokenize_normalizes_spaces_and_punctuation():
    assert tokenize("  경남,  창원시   의창구 ") == ["경남", "창원시", "의창구"]


def test_short_sido_alias_matches():
    hits = match_regions("경남 창원시 의창구", SIDOS)
    assert [r.code for r, _ in hits] == ["38"]


def test_full_sido_name_matches():
    hits = match_regions("서울특별시 종로구", SIDOS)
    assert hits[0][0].code == "11"


def test_no_sido_token_returns_empty():
    assert match_regions("의창구 팔용동", SIDOS) == []


def test_sigungu_specific_token_wins_over_shared_city():
    hits = match_regions("경남 창원시 의창구", SGGS)
    assert hits[0][0].code == "38111"
    assert len(hits) == 1  # 동점 후보만 돌려준다


def test_city_only_returns_all_ties():
    hits = match_regions("창원시", SGGS)
    assert sorted(r.code for r, _ in hits) == ["38111", "38112", "38113"]


def test_prefix_without_suffix_matches():
    hits = match_regions("진주", SGGS)
    assert hits[0][0].code == "38030"


def test_consumed_tokens_reported():
    hits = match_regions("경남 창원시 의창구 팔용동", SGGS)
    region, consumed = hits[0]
    assert region.code == "38111"
    assert set(consumed) == {"창원시", "의창구"}


def test_no_space_query_matches_by_substring():
    hits = match_regions("창원시의창구", SGGS)
    assert hits[0][0].code == "38111"
