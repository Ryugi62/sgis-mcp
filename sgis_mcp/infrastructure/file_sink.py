"""파일 쓰기 — 단계구분도 SVG를 폴더에 저장하고 절대 경로를 돌려준다."""
from __future__ import annotations

import os
import re


class DirFileSink:
    def __init__(self, folder: str):
        self.folder = folder

    def write_text(self, name: str, text: str) -> str:
        os.makedirs(self.folder, exist_ok=True)
        safe = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", os.path.basename(name)) or "map.svg"
        path = os.path.abspath(os.path.join(self.folder, safe))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path
