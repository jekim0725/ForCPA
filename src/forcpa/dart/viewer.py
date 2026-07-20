"""DART 공시 뷰어에서 감사보고서 첨부와 본문 구간을 선택한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs

from lxml import html as lxml_html

from .api_client import DartClient
from .document_parser import _decode


class AuditAttachmentNotFound(ValueError):
    """감사보고서 첨부 또는 독립된 감사인의 보고서 구간을 찾지 못한 경우."""


@dataclass(frozen=True, slots=True)
class AuditReportSource:
    attachment_name: str
    dcm_no: str
    report_scope: str
    html: bytes
    source_url: str
    source_locator: str


@dataclass(frozen=True, slots=True)
class _Attachment:
    name: str
    dcm_no: str
    report_scope: str
    score: int


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


class DartViewer:
    """OpenDART 원본 ZIP이 아니라 DART 뷰어의 선택된 첨부문서만 읽는다."""

    def __init__(self, client: DartClient) -> None:
        self.client = client

    @staticmethod
    def _select_attachment(page: bytes) -> _Attachment:
        try:
            root = lxml_html.fromstring(_decode(page))
        except (ValueError, TypeError) as exc:
            raise AuditAttachmentNotFound("DART 첨부 목록을 읽지 못했습니다.") from exc

        candidates: list[_Attachment] = []
        for option in root.xpath("//select[@id='att']/option"):
            value = option.get("value") or ""
            query = parse_qs(value)
            dcm_no = (query.get("dcmNo") or [""])[0]
            if not dcm_no:
                continue
            raw_name = "".join(option.itertext())
            name = re.sub(r"^\s*\d{4}[.]\d{2}[.]\d{2}", "", raw_name).strip()
            compact_name = _compact(name)

            if compact_name == "연결감사보고서":
                candidates.append(_Attachment("연결감사보고서", dcm_no, "consolidated", 100))
            elif compact_name == "감사보고서":
                candidates.append(_Attachment("감사보고서", dcm_no, "separate", 80))
            elif "연결감사보고서" in compact_name and "내부회계" not in compact_name:
                candidates.append(_Attachment(name, dcm_no, "consolidated", 90))
            elif compact_name.endswith("감사보고서") and not any(
                excluded in compact_name for excluded in ("감사의감사보고서", "내부회계", "감사위원회")
            ):
                candidates.append(_Attachment(name, dcm_no, "separate", 60))

        if not candidates:
            raise AuditAttachmentNotFound("DART 첨부 목록에서 감사보고서를 찾지 못했습니다.")
        return max(candidates, key=lambda item: item.score)

    @staticmethod
    def _select_audit_section(page: bytes) -> dict[str, str]:
        script = _decode(page)
        nodes: list[dict[str, str]] = []
        text_pattern = re.compile(r"node\d+\['text'\]\s*=\s*\"(?P<text>[^\"]+)\";")
        for match in text_pattern.finditer(script):
            snippet = script[match.end() : match.end() + 2200]
            node = {"text": match.group("text")}
            for key in ("rcpNo", "dcmNo", "eleId", "offset", "length", "dtd"):
                value_match = re.search(rf"node\d+\['{key}'\]\s*=\s*\"([^\"]+)\";", snippet)
                node[key] = value_match.group(1) if value_match else ""
            nodes.append(node)

        exact = [node for node in nodes if _compact(node["text"]) == "독립된감사인의감사보고서"]
        candidates = exact or [
            node
            for node in nodes
            if "독립된감사인의감사보고서" in _compact(node["text"])
            and "내부회계" not in _compact(node["text"])
        ]
        if not candidates:
            raise AuditAttachmentNotFound("첨부문서에서 독립된 감사인의 감사보고서 목차를 찾지 못했습니다.")
        selected = candidates[0]
        required = ("rcpNo", "dcmNo", "eleId", "offset", "length", "dtd")
        if any(not selected.get(key) for key in required):
            raise AuditAttachmentNotFound("감사보고서 본문 요청정보가 불완전합니다.")
        return {key: selected[key] for key in required}

    def load_audit_report(self, rcept_no: str) -> AuditReportSource:
        filing_page = self.client.get_filing_viewer(rcept_no)
        attachment = self._select_attachment(filing_page)
        attachment_page = self.client.get_filing_viewer(rcept_no, attachment.dcm_no)
        section_params = self._select_audit_section(attachment_page)
        report_html = self.client.get_report_viewer(section_params)
        source_url = (
            f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
            f"&dcmNo={attachment.dcm_no}"
        )
        return AuditReportSource(
            attachment_name=attachment.name,
            dcm_no=attachment.dcm_no,
            report_scope=attachment.report_scope,
            html=report_html,
            source_url=source_url,
            source_locator=(
                f"{attachment.name} (dcmNo={attachment.dcm_no}) / "
                f"독립된 감사인의 감사보고서 (eleId={section_params['eleId']})"
            ),
        )
