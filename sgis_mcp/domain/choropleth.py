"""단계구분도(SVG) — 경계(UTM-K 미터 좌표) + 값 → 5분위 채색 지도. 외부 라이브러리 0 (SPEC S5).

UTM-K(EPSG:5179)는 평면 미터 좌표라 투영 변환 없이 축척만 맞추면 된다. y는 북쪽이 크므로 화면에선 뒤집는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

Ring = List[Tuple[float, float]]
PALETTE = ["#E8F3FF", "#C9E2FF", "#90C2FF", "#3182F6", "#1B64DA"]  # 연한 → 진한(한 색상 계열)
NO_DATA = "#E5E8EB"
INK, SUB = "#191F28", "#4E5968"
FONT = "Pretendard, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"


@dataclass
class Feature:
    adm_cd: str
    adm_nm: str
    rings: List[Ring]

    @property
    def short_name(self) -> str:
        parts = (self.adm_nm or "").split()
        return parts[-1] if parts else self.adm_cd


def features_from_geojson(gj: dict) -> List[Feature]:
    out = []
    for f in gj.get("features") or []:
        g = f.get("geometry") or {}
        props = f.get("properties") or {}
        polys = []
        if g.get("type") == "Polygon":
            polys = [g.get("coordinates") or []]
        elif g.get("type") == "MultiPolygon":
            polys = g.get("coordinates") or []
        rings = [[(float(p[0]), float(p[1])) for p in ring] for poly in polys for ring in poly if ring]
        out.append(Feature(str(props.get("adm_cd", "")), str(props.get("adm_nm", "")), rings))
    return out


def quantile_breaks(values: Sequence[Optional[float]], k: int = 5) -> List[float]:
    """분위 상한 목록(중복 제거). 값이 k개보다 적은 고유값이면 그 수만큼."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return []
    n = len(vals)
    breaks: List[float] = []
    for i in range(1, k + 1):
        idx = max(0, min(n - 1, int(round(i * n / k)) - 1))
        b = vals[idx]
        if not breaks or b > breaks[-1]:
            breaks.append(b)
    if breaks[-1] < vals[-1]:
        breaks[-1] = vals[-1]
    return breaks


def class_index(v: Optional[float], breaks: Sequence[float]) -> Optional[int]:
    if v is None or not breaks:
        return None
    for i, b in enumerate(breaks):
        if v <= b:
            return i
    return len(breaks) - 1


def _fmt(v: float) -> str:
    if v is None:
        return "-"
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}"
    return f"{v:,.1f}"


def _ring_area_centroid(ring: Ring) -> Tuple[float, float, float]:
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-12:
        xs, ys = [p[0] for p in ring], [p[1] for p in ring]
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return abs(a), cx / (6 * a), cy / (6 * a)


def _em(text: str) -> float:
    """글자 폭 어림(em): 한글·한자 1.0, 그 밖 0.56."""
    return sum(1.0 if ord(ch) > 0x2E80 else 0.56 for ch in text)


def wrap_units(text: str, max_em: float) -> List[str]:
    """출처 줄을 폭(max_em) 안으로 나눈다 — ' · '·', '·공백 경계에서 끊고, 내용은 그대로 둔다."""
    import re
    parts = [p for p in re.split(r"(?<=[·,]) |(?= · )| ", text or "") if p != ""]
    lines, cur = [], ""
    for p in parts:
        cand = (cur + " " + p) if cur else p
        if cur and _em(cand) > max_em:
            lines.append(cur)
            cur = p.lstrip()
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines or [""]


def render_svg(features: Sequence[Feature], values: Dict[str, Optional[float]], title: str, unit: str,
               source: str, subtitle: str = "", width: int = 820, label_limit: int = 40) -> str:
    pts = [p for f in features for r in f.rings for p in r]
    if not pts:
        raise ValueError("경계 좌표가 없습니다")
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)
    pad, header = 24, 78 if subtitle else 58
    legend_w = 190
    map_w = width - pad * 2 - legend_w
    bw, bh = max(maxx - minx, 1e-9), max(maxy - miny, 1e-9)
    scale = map_w / bw
    map_h = bh * scale
    if map_h > 900:  # 세로로 긴 지역은 높이 기준으로 줄인다
        scale = 900 / bh
        map_h = 900.0
    src_lines = wrap_units(source, (width - pad * 2) / 10.5)
    height = int(header + map_h + pad + 40 + 15 * (len(src_lines) - 1))

    def tx(x: float) -> float:
        return pad + (x - minx) * scale

    def ty(y: float) -> float:
        return header + (maxy - y) * scale

    breaks = quantile_breaks([values.get(f.adm_cd) for f in features], len(PALETTE))
    colors = PALETTE if len(breaks) >= len(PALETTE) else PALETTE[len(PALETTE) - len(breaks):]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
           f'font-family="{escape(FONT)}">',
           f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
           f'<text x="{pad}" y="34" font-size="20" font-weight="700" fill="{INK}">{escape(title)}</text>']
    if subtitle:
        out.append(f'<text x="{pad}" y="58" font-size="12.5" fill="{SUB}">{escape(subtitle)}</text>')
    labels = []
    for f in features:
        v = values.get(f.adm_cd)
        ci = class_index(v, breaks)
        fill = NO_DATA if ci is None else colors[ci]
        d = []
        for ring in f.rings:
            last = None
            seg = []
            for x, y in ring:
                px, py = round(tx(x), 1), round(ty(y), 1)
                if last is not None and abs(px - last[0]) < 0.5 and abs(py - last[1]) < 0.5:
                    continue
                seg.append(f"{px} {py}")
                last = (px, py)
            if len(seg) >= 3:
                d.append("M" + " L".join(seg) + " Z")
        out.append(f'<path data-adm="{escape(f.adm_cd)}" d="{" ".join(d)}" fill="{fill}" fill-rule="evenodd" '
                   f'stroke="#FFFFFF" stroke-width="0.8"><title>{escape(f.adm_nm)}: {escape(_fmt(v))}{escape(unit)}</title></path>')
        if f.rings:
            area, cx, cy = max((_ring_area_centroid(r) for r in f.rings), key=lambda t: t[0])
            dark = ci is not None and ci >= len(colors) - 2
            labels.append((tx(cx), ty(cy), f.short_name, "#FFFFFF" if dark else INK))
    if len(features) <= label_limit:
        for x, y, name, color in labels:
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="10.5" text-anchor="middle" fill="{color}">'
                       f'{escape(name)}</text>')
    # 범례
    lx, ly = width - pad - legend_w + 16, header + 4
    out.append(f'<text x="{lx}" y="{ly + 10}" font-size="12" font-weight="700" fill="{INK}">범례{(" (" + escape(unit) + ")") if unit else ""}</text>')
    lo = min((v for v in values.values() if v is not None), default=None)
    prev = lo
    for i, b in enumerate(breaks):
        yy = ly + 24 + i * 24
        if i == 0:
            rng = _fmt(b) if prev == b else f"{_fmt(prev)} ~ {_fmt(b)}"
        else:
            rng = f"{_fmt(prev)} 초과 ~ {_fmt(b)}"
        out.append(f'<rect x="{lx}" y="{yy}" width="18" height="16" rx="3" fill="{colors[i]}"/>')
        out.append(f'<text x="{lx + 26}" y="{yy + 12.5}" font-size="11.5" fill="{INK}">{escape(rng)}</text>')
        prev = b
    if any(values.get(f.adm_cd) is None for f in features):
        yy = ly + 24 + len(breaks) * 24
        out.append(f'<rect x="{lx}" y="{yy}" width="18" height="16" rx="3" fill="{NO_DATA}"/>')
        out.append(f'<text x="{lx + 26}" y="{yy + 12.5}" font-size="11.5" fill="{SUB}">자료 없음</text>')
    for i, line in enumerate(src_lines):
        yy = height - 16 - 15 * (len(src_lines) - 1 - i)
        out.append(f'<text x="{pad}" y="{yy}" class="src" font-size="10.5" fill="{SUB}">{escape(line)}</text>')
    out.append("</svg>")
    return "\n".join(out)
