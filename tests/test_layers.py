"""레이어 규칙 — domain ← application ← adapters ← infrastructure, 역방향 import 0 (SPEC §7)."""
import ast
import os

from tests.conftest import ROOT

ORDER = ["domain", "application", "adapters", "infrastructure"]
PKG = os.path.join(ROOT, "sgis_mcp")


def _imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level:  # 상대 import → 패키지 기준 경로로
                yield node.level, mod
            else:
                yield 0, mod
        elif isinstance(node, ast.Import):
            for a in node.names:
                yield 0, a.name


def _target_layer(src_layer, level, mod):
    if level == 0:
        parts = mod.split(".")
        return parts[1] if parts[0] == "sgis_mcp" and len(parts) > 1 else None
    if level == 1:
        return src_layer
    if level >= 2:
        return mod.split(".")[0] if mod else None
    return None


def test_no_reverse_layer_imports():
    bad = []
    for layer in ORDER:
        d = os.path.join(PKG, layer)
        for f in os.listdir(d):
            if not f.endswith(".py"):
                continue
            for level, mod in _imports(os.path.join(d, f)):
                tgt = _target_layer(layer, level, mod)
                if tgt in ORDER and ORDER.index(tgt) > ORDER.index(layer):
                    bad.append(f"{layer}/{f} → {tgt}")
    assert bad == []


def test_domain_has_no_io_modules():
    forbidden = {"urllib", "http", "socket", "subprocess", "json", "os", "sys"}
    d = os.path.join(PKG, "domain")
    for f in os.listdir(d):
        if f.endswith(".py"):
            mods = {m.split(".")[0] for lvl, m in _imports(os.path.join(d, f)) if lvl == 0}
            assert not (mods & forbidden), (f, mods & forbidden)
