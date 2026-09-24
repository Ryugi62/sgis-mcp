"""설정 — 환경변수가 우선, 없으면 KEY=VALUE 파일(--env-file 또는 SGIS_ENV_FILE)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

from ..adapters.sgis_gateway import DEFAULT_BASE


@dataclass
class Settings:
    consumer_key: str
    consumer_secret: str
    base_url: str
    out_dir: str
    log_path: Optional[str]
    fixtures_dir: Optional[str]


def load_env_file(path: Optional[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def load_settings(env_file: Optional[str] = None, environ: Mapping[str, str] = os.environ,
                  fixtures: Optional[str] = None, out_dir: Optional[str] = None) -> Settings:
    file_vals = load_env_file(env_file or environ.get("SGIS_ENV_FILE"))

    def get(k: str, default: Optional[str] = None) -> Optional[str]:
        return environ.get(k) or file_vals.get(k) or default

    return Settings(consumer_key=get("SGIS_CONSUMER_KEY", "") or "",
                    consumer_secret=get("SGIS_CONSUMER_SECRET", "") or "",
                    base_url=get("SGIS_BASE_URL", DEFAULT_BASE) or DEFAULT_BASE,
                    out_dir=out_dir or get("SGIS_MCP_OUT") or os.path.join(os.path.expanduser("~"), "sgis-mcp-maps"),
                    log_path=get("SGIS_MCP_LOG"),
                    fixtures_dir=fixtures or get("SGIS_MCP_FIXTURES"))
