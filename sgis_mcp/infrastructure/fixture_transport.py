"""가짜 응답 전송 — 폴더의 JSON을 SGIS 응답처럼 돌려준다(키 없이 부팅·체험·테스트용).

파일 이름: 확장자를 뗀 경로의 '/'를 '__'로 바꾸고, 구체적인 파라미터가 있으면 `__<키>=<값>`을 붙인다.
예) addr/stage.json + cd=38 → addr__stage__cd=38.json(없으면 addr__stage.json).
결과에는 항상 `_fixture` 표시가 붙어 출처에 「가짜 응답」이 찍힌다.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Tuple

SPECIFIC_KEYS = ("cd", "adm_cd", "class_code", "address")


class FixtureTransport:
    def __init__(self, folder: str):
        self.folder = folder

    def get(self, url: str, params: Dict[str, str], timeout: float) -> Tuple[int, bytes]:
        path = url.split("/OpenAPI3/", 1)[-1]
        if path == "auth/authentication.json":
            body = {"id": "API_0101", "errCd": 0, "errMsg": "Success", "trId": "fixture_API_0101",
                    "result": {"accessToken": "fixture-token", "accessTimeout": "4102444800000"}, "_fixture": "auth"}
            return 200, json.dumps(body).encode("utf-8")
        flat = os.path.splitext(path)[0].replace("/", "__")
        names = [f"{flat}__{k}={params[k]}.json" for k in SPECIFIC_KEYS if k in params] + [f"{flat}.json"]
        for n in names:
            p = os.path.join(self.folder, n)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                data.setdefault("_fixture", n)
                return 200, json.dumps(data, ensure_ascii=False).encode("utf-8")
        body = {"errCd": -100, "errMsg": "검색결과가 존재하지 않습니다(가짜 응답 없음)", "id": None,
                "trId": "fixture_none", "_fixture": "none"}
        return 200, json.dumps(body, ensure_ascii=False).encode("utf-8")
