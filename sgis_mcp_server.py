#!/usr/bin/env python3
"""SGIS MCP 서버(표준 입출력). 설치 0 — 파이썬 3.9+ 표준 라이브러리만.

    SGIS_CONSUMER_KEY=… SGIS_CONSUMER_SECRET=… python3 sgis_mcp_server.py
    python3 sgis_mcp_server.py --fixtures tests/fixtures     # 키 없이 체험(가짜 응답 표시)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sgis_mcp.infrastructure.main import main  # noqa: E402

if __name__ == "__main__":
    main()
