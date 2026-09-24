"""호출 기록(JSONL) — 활용 성과의 근거자료. 비밀값(토큰·키)은 받지 않는다(게이트웨이가 거른다)."""
from __future__ import annotations

import datetime as _dt
import json
import os


class JsonlLog:
    def __init__(self, path: str):
        self.path = path

    def append(self, record: dict) -> None:
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        row = dict(record, ts=_dt.datetime.now(_dt.timezone.utc).astimezone().isoformat(timespec="seconds"))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
