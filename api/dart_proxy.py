"""서울 리전에서 OpenDART와 DART 뷰어 요청만 중계하는 Vercel 함수."""

from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler
from typing import Any

import requests


UPSTREAMS = {
    "opendart": {
        "base_url": "https://opendart.fss.or.kr",
        "paths": {"/api/corpCode.xml", "/api/list.json", "/api/document.xml"},
        "needs_api_key": True,
    },
    "dart": {
        "base_url": "https://dart.fss.or.kr",
        "paths": {"/dsaf001/main.do", "/report/viewer.do"},
        "needs_api_key": False,
    },
}
MAX_REQUEST_BYTES = 32 * 1024


def prepare_upstream(payload: object, api_key: str) -> tuple[str, dict[str, Any]]:
    """허용 목록에 있는 고정 DART 주소만 조합한다."""
    if not isinstance(payload, dict):
        raise ValueError("요청 본문은 JSON 객체여야 합니다.")
    target = payload.get("target")
    path = payload.get("path")
    params = payload.get("params", {})
    config = UPSTREAMS.get(target) if isinstance(target, str) else None
    if config is None or not isinstance(path, str) or path not in config["paths"]:
        raise ValueError("허용되지 않은 DART 요청입니다.")
    if not isinstance(params, dict) or len(params) > 50:
        raise ValueError("요청 변수가 올바르지 않습니다.")

    clean_params: dict[str, Any] = {}
    for key, value in params.items():
        if not isinstance(key, str) or key == "crtfc_key":
            continue
        if isinstance(value, (str, int, float, bool)):
            clean_params[key] = value
        else:
            raise ValueError("요청 변수 형식이 올바르지 않습니다.")

    if config["needs_api_key"]:
        if not api_key:
            raise RuntimeError("Vercel에 DART_API_KEY가 설정되지 않았습니다.")
        clean_params["crtfc_key"] = api_key
    return f"{config['base_url']}{path}", clean_params


class handler(BaseHTTPRequestHandler):
    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        expected = os.getenv("DART_PROXY_TOKEN", "").strip()
        if not expected:
            self._write_json(503, {"error": "DART_PROXY_TOKEN is not configured"})
            return False
        supplied = self.headers.get("Authorization", "")
        if not supplied.startswith("Bearer ") or not hmac.compare_digest(
            supplied.removeprefix("Bearer "), expected
        ):
            self._write_json(401, {"error": "unauthorized"})
            return False
        return True

    def do_GET(self) -> None:
        """배포 후 DART 뷰어 연결 여부를 확인하는 인증된 진단 요청."""
        if not self._authorized():
            return
        try:
            response = requests.get(
                "https://dart.fss.or.kr/dsaf001/main.do",
                timeout=(5, 15),
                allow_redirects=False,
                headers={"User-Agent": "forcpa-dart-proxy/1.0"},
            )
        except requests.RequestException:
            self._write_json(504, {"ok": False, "error": "DART connection failed"})
            return
        self._write_json(
            200,
            {"ok": response.status_code < 500, "upstream_status": response.status_code},
        )

    def do_POST(self) -> None:
        if not self._authorized():
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self._write_json(400, {"error": "invalid request size"})
            return

        try:
            payload = json.loads(self.rfile.read(content_length))
            url, params = prepare_upstream(payload, os.getenv("DART_API_KEY", "").strip())
        except ValueError as exc:
            self._write_json(400, {"error": str(exc)})
            return
        except RuntimeError as exc:
            self._write_json(503, {"error": str(exc)})
            return

        try:
            response = requests.get(
                url,
                params=params,
                timeout=(5, 45),
                allow_redirects=False,
                headers={"User-Agent": "forcpa-dart-proxy/1.0"},
            )
        except requests.ConnectTimeout:
            self._write_json(504, {"error": "DART connection timed out"})
            return
        except requests.RequestException:
            self._write_json(502, {"error": "DART request failed"})
            return

        self.send_response(response.status_code)
        self.send_header("Content-Type", response.headers.get("Content-Type", "application/octet-stream"))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-ForCPA-Proxy", "vercel-icn1")
        self.end_headers()
        self.wfile.write(response.content)
