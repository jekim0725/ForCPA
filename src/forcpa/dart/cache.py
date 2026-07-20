"""접수번호별 KAM 결과 JSON 캐시."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import KamResult


class ResultCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, rcept_no: str) -> Path:
        if not re.fullmatch(r"\d{14}", rcept_no):
            raise ValueError("올바르지 않은 DART 접수번호입니다.")
        return self.directory / f"{rcept_no}.json"

    def load(self, rcept_no: str, *, parser_version: str) -> KamResult | None:
        path = self._path(rcept_no)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("parser_version") != parser_version:
                return None
            result = KamResult.from_dict(payload)
            result.from_cache = True
            return result
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def save(self, result: KamResult) -> Path:
        path = self._path(result.rcept_no)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
        return path
