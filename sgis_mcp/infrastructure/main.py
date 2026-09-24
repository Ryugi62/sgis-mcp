"""조립(composition root) — 설정을 읽어 전송·게이트웨이·서비스·MCP 서버를 잇고 stdin/stdout으로 돈다."""
from __future__ import annotations

import argparse
import io
import sys
from typing import Optional, Sequence

from ..adapters.mcp_stdio import McpServer, serve
from ..adapters.sgis_gateway import SgisHttpGateway
from ..application.service import SgisService
from .call_log import JsonlLog
from .config import Settings, load_settings
from .file_sink import DirFileSink
from .fixture_transport import FixtureTransport
from .urllib_transport import UrllibTransport


def build(settings: Settings) -> McpServer:
    log = JsonlLog(settings.log_path).append if settings.log_path else None
    if settings.fixtures_dir:
        transport, key, secret = FixtureTransport(settings.fixtures_dir), "fixture", "fixture"
    else:
        transport, key, secret = UrllibTransport(), settings.consumer_key, settings.consumer_secret
    gateway = SgisHttpGateway(transport, key, secret, base_url=settings.base_url, on_call=log)
    return McpServer(SgisService(gateway, DirFileSink(settings.out_dir)), on_tool=log)


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="SGIS MCP 서버(stdio) — 국가데이터처 통계지리정보서비스 OpenAPI")
    ap.add_argument("--env-file", help="SGIS_CONSUMER_KEY=… / SGIS_CONSUMER_SECRET=… 가 든 파일")
    ap.add_argument("--fixtures", help="가짜 응답 폴더(키 없이 체험·테스트) — 결과에 「가짜 응답」 표시")
    ap.add_argument("--out", help="단계구분도 SVG 저장 폴더(기본 ~/sgis-mcp-maps)")
    a = ap.parse_args(argv)
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8") if hasattr(sys.stdin, "buffer") else sys.stdin
    stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8") if hasattr(sys.stdout, "buffer") else sys.stdout
    serve(stdin, stdout, build(load_settings(a.env_file, fixtures=a.fixtures, out_dir=a.out)))
