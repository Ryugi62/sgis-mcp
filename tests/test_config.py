"""설정 로딩 — 환경변수 우선, 파일 보조."""
from sgis_mcp.infrastructure.config import load_env_file, load_settings


def test_env_file_parsing(tmp_path):
    p = tmp_path / "sgis.env"
    p.write_text("# 주석\nSGIS_CONSUMER_KEY='abc'\nSGIS_CONSUMER_SECRET=\"def\"\n\nBAD LINE\n", encoding="utf-8")
    assert load_env_file(str(p)) == {"SGIS_CONSUMER_KEY": "abc", "SGIS_CONSUMER_SECRET": "def"}


def test_environ_wins_over_file(tmp_path):
    p = tmp_path / "sgis.env"
    p.write_text("SGIS_CONSUMER_KEY=file\nSGIS_CONSUMER_SECRET=filesecret\n", encoding="utf-8")
    s = load_settings(str(p), environ={"SGIS_CONSUMER_KEY": "env"})
    assert s.consumer_key == "env" and s.consumer_secret == "filesecret"
    assert s.base_url == "https://sgisapi.mods.go.kr/OpenAPI3"


def test_defaults_without_anything():
    s = load_settings(None, environ={})
    assert s.consumer_key == "" and s.fixtures_dir is None and s.out_dir.endswith("sgis-mcp-maps")
