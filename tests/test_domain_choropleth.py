"""단계구분도(SVG) — UC-12 순수 부분."""
import xml.etree.ElementTree as ET

from sgis_mcp.domain.choropleth import (PALETTE, Feature, class_index, features_from_geojson, quantile_breaks,
                                        render_svg)

SQ = lambda x0, y0, s=100: [[(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s), (x0, y0)]]


def _features():
    return [Feature("A", "가동", SQ(0, 0)), Feature("B", "나동", SQ(100, 0)), Feature("C", "다동", SQ(200, 0)),
            Feature("D", "라동", SQ(0, 100)), Feature("E", "마동", SQ(100, 100))]


def test_quantile_breaks_five_classes():
    b = quantile_breaks([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5)
    assert b == [2, 4, 6, 8, 10]


def test_quantile_breaks_dedupes_and_skips_none():
    assert quantile_breaks([5, 5, 5, None], 5) == [5]
    assert quantile_breaks([], 5) == []


def test_class_index():
    b = [2, 4, 6, 8, 10]
    assert class_index(1, b) == 0 and class_index(2, b) == 0 and class_index(3, b) == 1 and class_index(10, b) == 4
    assert class_index(None, b) is None


def test_features_from_geojson_polygon_and_multipolygon():
    gj = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]},
         "properties": {"adm_cd": "1", "adm_nm": "서울특별시 성동구 왕십리2동"}},
        {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [0, 1], [0, 0]]],
                                                                               [[[5, 5], [6, 5], [5, 6], [5, 5]]]]},
         "properties": {"adm_cd": "2", "adm_nm": "섬"}}]}
    fs = features_from_geojson(gj)
    assert [f.adm_cd for f in fs] == ["1", "2"]
    assert fs[0].short_name == "왕십리2동"
    assert len(fs[1].rings) == 2


def test_render_svg_is_valid_xml_with_legend_and_source():
    vals = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": None}
    svg = render_svg(_features(), vals, title="테스트 지도", unit="%", source="출처: 국가데이터처 SGIS")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert svg.count("<path") == 5
    assert "테스트 지도" in svg and "출처: 국가데이터처 SGIS" in svg and "자료 없음" in svg
    assert PALETTE[-1] in svg  # 최고 분위 색이 쓰였다


def test_render_svg_flips_y_axis_north_up():
    fs = [Feature("S", "남", SQ(0, 0)), Feature("N", "북", SQ(0, 1000))]
    svg = render_svg(fs, {"S": 1, "N": 2}, title="t", unit="", source="s")
    import re
    ys = {}
    for m in re.finditer(r'<path data-adm="(\w)" d="M[\d.]+ ([\d.]+)', svg):
        ys[m.group(1)] = float(m.group(2))
    assert ys["N"] < ys["S"]  # 북쪽이 화면 위


def test_render_svg_escapes_names():
    fs = [Feature("A", "<&>", SQ(0, 0))]
    svg = render_svg(fs, {"A": 1}, title="a&b", unit="", source="s")
    ET.fromstring(svg)
    assert "a&amp;b" in svg
