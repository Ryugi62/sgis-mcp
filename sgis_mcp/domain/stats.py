"""통계행 파싱 · 필드 이름(문서 표기 그대로) · 코드표(개발지원센터 dataCode, 2026-09-24)."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from .errors import InvalidArgument

FIELD_LABELS: Dict[str, str] = {
    # stats/population.json (총조사 주요지표)
    "tot_ppltn": "총인구", "avg_age": "평균나이(세)", "ppltn_dnsty": "인구밀도(명/㎢)",
    "aged_child_idx": "노령화지수(일백명당 명)", "oldage_suprt_per": "노년부양비(일백명당 명)",
    "juv_suprt_per": "유년부양비(일백명당 명)", "tot_family": "총가구", "avg_fmember_cnt": "평균가구원수",
    "tot_house": "총주택", "nongga_cnt": "농가(가구)", "nongga_ppltn": "농가 인구", "imga_cnt": "임가(가구)",
    "imga_ppltn": "임가 인구", "naesuoga_cnt": "내수면 어가(가구)", "naesuoga_ppltn": "내수면 어가 인구",
    "haesuoga_cnt": "해수면 어가(가구)", "haesuoga_ppltn": "해수면 어가인구",
    "employee_cnt": "종업원수(전체 사업체)", "corp_cnt": "사업체수(전체 사업체)",
    # searchpopulation / household / house / company
    "population": "인구수", "household_cnt": "가구수", "family_member_cnt": "총 가구원 수",
    "avg_family_member_cnt": "평균가구원수", "house_cnt": "주택수(호)", "tot_worker": "종사자수(명)",
}
SUMMARY_FIELDS = ["tot_ppltn", "avg_age", "ppltn_dnsty", "aged_child_idx", "oldage_suprt_per", "juv_suprt_per",
                  "tot_family", "avg_fmember_cnt", "tot_house", "corp_cnt", "employee_cnt"]

AGE_TYPES: Dict[str, str] = {
    "01": "0~4세", "02": "5~9세", "03": "10~14세", "04": "15~19세", "05": "20~24세", "06": "25~29세",
    "07": "30~34세", "08": "35~39세", "09": "40~44세", "10": "45~49세", "11": "50~54세", "12": "55~59세",
    "13": "60~64세", "14": "65~69세", "15": "70~74세", "16": "75~79세", "17": "80~84세", "18": "85~89세",
    "19": "90~94세", "20": "95~99세", "21": "100세 이상", "22": "15세미만", "23": "15~64세", "24": "65세이상",
    "25": "85세이상", "26": "유아(0~7세)", "27": "초(8~13세)", "28": "중(14~16세)", "29": "고(17~19세)",
    "30": "10대이하", "31": "10대", "32": "20대", "33": "30대", "34": "40대", "35": "50대", "36": "60대",
    "37": "70대", "38": "80대", "39": "90대", "40": "70대이상", "41": "80대이상",
}
HOUSEHOLD_TYPES: Dict[str, str] = {"01": "1세대가구", "02": "2세대가구", "03": "3세대가구", "04": "4세대가구",
                                   "05": "5세대이상가구", "A0": "1인가구", "B0": "비혈연가구"}
HOUSE_TYPES: Dict[str, str] = {"01": "단독주택", "02": "아파트", "03": "연립주택", "04": "다세대주택",
                               "05": "비거주용 건물(상가,공장,여관 등)내 주택"}
_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+\.\d+$")


def parse_number(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if s in ("", "N/A", "null", "NULL", "-"):
        return None
    if _INT.match(s):
        return int(s)
    if _FLOAT.match(s):
        return float(s)
    return s


def parse_rows(result: Optional[Iterable[dict]], fields: Optional[Sequence[str]] = None) -> List[dict]:
    rows = []
    for item in result or []:
        row = {"adm_cd": str(item.get("adm_cd", "")), "adm_nm": item.get("adm_nm")}
        keys = fields if fields is not None else [k for k in item if k not in ("adm_cd", "adm_nm")]
        for k in keys:
            row[k] = parse_number(item.get(k))
        rows.append(row)
    return rows


def class_deg_for_year(year: int) -> str:
    y = int(year)
    if y <= 2005:
        return "8"
    if y <= 2016:
        return "9"
    if y <= 2023:
        return "10"
    return "11"


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s))


def _resolve(value: Union[str, Sequence[str], None], table: Dict[str, str], what: str, upper: bool = False) -> Optional[str]:
    if value is None or value == "" or value == []:
        return None
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    by_name = {_norm(v): k for k, v in table.items()}
    out = []
    for raw in items:
        s = str(raw).strip()
        key = s.upper() if upper else s
        if key in table:
            out.append(key)
        elif _norm(s) in by_name:
            out.append(by_name[_norm(s)])
        else:
            raise InvalidArgument(f"{what} 코드를 모릅니다: {s!r} — 가능한 값: " +
                                  ", ".join(f"{k}={v}" for k, v in table.items()))
    return ",".join(out)


def resolve_age_type(value) -> Optional[str]:
    return _resolve(value, AGE_TYPES, "연령타입(age_type)")


def resolve_household_type(value) -> Optional[str]:
    return _resolve(value, HOUSEHOLD_TYPES, "세대구성(household_type)", upper=True)


def resolve_house_type(value) -> Optional[str]:
    return _resolve(value, HOUSE_TYPES, "주택유형(house_type)")
