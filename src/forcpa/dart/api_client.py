"""OpenDART HTTP API의 작은 래퍼."""

from __future__ import annotations

import time
from typing import Any
from xml.etree import ElementTree

import requests


class DartApiError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"OpenDART 오류 {code}: {message}")


class DartClient:
    BASE_URL = "https://opendart.fss.or.kr/api"
    DART_VIEWER_BASE_URL = "https://dart.fss.or.kr"

    def __init__(
        self,
        api_key: str,
        *,
        timeout: tuple[float, float] = (5.0, 30.0),
        max_retries: int = 2,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DART_API_KEY가 필요합니다.")
        self._api_key = api_key.strip()
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "forcpa-dart-kam/1.0"})

    def _send(self, url: str, params: dict[str, Any]) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                )
                if response.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(0.5 * (2**attempt))
        # requests 예외에는 쿼리 문자열의 인증키가 포함될 수 있으므로 원문을 노출하지 않는다.
        raise DartApiError("network_error", "네트워크 요청에 실패했습니다.") from last_error

    def _request(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        safe_params = {**params, "crtfc_key": self._api_key}
        return self._send(f"{self.BASE_URL}/{endpoint}", safe_params)

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._request(endpoint, params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise DartApiError("invalid_response", "JSON 응답을 해석하지 못했습니다.") from exc
        status = str(payload.get("status", ""))
        if status == "013":
            return {"status": status, "list": []}
        if status != "000":
            raise DartApiError(status or "unknown", str(payload.get("message", "알 수 없는 오류")))
        return payload

    @staticmethod
    def _raise_if_xml_error(content: bytes) -> None:
        stripped = content.lstrip()
        if not stripped.startswith(b"<"):
            return
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError:
            return
        status = root.findtext("status") or ""
        if status and status != "000":
            raise DartApiError(status, root.findtext("message") or "알 수 없는 오류")

    def download_corp_codes(self) -> bytes:
        content = self._request("corpCode.xml", {}).content
        self._raise_if_xml_error(content)
        return content

    def list_annual_reports(self, corp_code: str, begin_date: str, end_date: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            "list.json",
            {
                "corp_code": corp_code,
                "bgn_de": begin_date,
                "end_de": end_date,
                "last_reprt_at": "Y",
                "pblntf_ty": "A",
                "pblntf_detail_ty": "A001",
                "sort": "date",
                "sort_mth": "desc",
                "page_count": 100,
            },
        )
        return list(payload.get("list", []))

    def download_document(self, rcept_no: str) -> bytes:
        content = self._request("document.xml", {"rcept_no": rcept_no}).content
        self._raise_if_xml_error(content)
        return content

    def get_filing_viewer(self, rcept_no: str, dcm_no: str = "") -> bytes:
        params = {"rcpNo": rcept_no}
        if dcm_no:
            params["dcmNo"] = dcm_no
        return self._send(f"{self.DART_VIEWER_BASE_URL}/dsaf001/main.do", params).content

    def get_report_viewer(self, params: dict[str, str]) -> bytes:
        return self._send(f"{self.DART_VIEWER_BASE_URL}/report/viewer.do", params).content
