"""라이브 검증 스크립트가 가짜 응답으로 끝까지 돌고, 가짜 표시를 기록에 남기는지(네트워크 0)."""
import importlib.util
import os

from tests.conftest import FIXTURES, ROOT


def _load():
    spec = importlib.util.spec_from_file_location("live_smoke", os.path.join(ROOT, "scripts", "live_smoke.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_live_smoke_with_fixtures_writes_marked_record(tmp_path):
    m = _load()
    rc = m.main(["--fixtures", FIXTURES, "--region", "경남 창원시 의창구", "--address", "대전 서구 청사로 189",
                 "--out", str(tmp_path)])
    md = open(tmp_path / "live-check-fixture.md", encoding="utf-8").read()
    assert "가짜 응답(fixtures)" in md
    assert md.count("| `sgis_") == 12
    assert "fx_API_0704" in md  # 경계 trId가 기록된다
    assert rc in (0, 1)
    assert not os.path.exists(tmp_path / "live-check.md")  # 가짜 기록이 실제 기록 이름을 쓰지 않는다
