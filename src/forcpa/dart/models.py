"""앱 전체에서 공유하는 간단한 KAM 결과 모델."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class ResultStatus(StrEnum):
    SUCCESS = "success"
    COMPANY_NOT_FOUND = "company_not_found"
    ANNUAL_REPORT_NOT_FOUND = "annual_report_not_found"
    SOURCE_DOWNLOAD_FAILED = "source_download_failed"
    AUDIT_REPORT_NOT_IDENTIFIED = "audit_report_not_identified"
    KAM_NOT_PRESENT = "kam_not_present"
    PARSE_FAILED = "parse_failed"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


@dataclass(frozen=True, slots=True)
class Company:
    corp_code: str
    corp_name: str
    stock_code: str
    modify_date: str = ""


@dataclass(frozen=True, slots=True)
class Filing:
    rcept_no: str
    report_name: str
    report_period_end: str
    rcept_date: str
    is_amended: bool
    source_url: str


@dataclass(slots=True)
class KamItem:
    kam_no: int
    kam_title: str
    why_kam: str
    audit_response: str
    raw_text: str
    source_locator: str = ""


@dataclass(slots=True)
class KamResult:
    corp_code: str
    stock_code: str
    corp_name: str
    rcept_no: str
    report_name: str
    report_period_end: str
    rcept_date: str
    is_amended: bool
    report_scope: str
    auditor_name: str
    status: ResultStatus
    confidence: str
    source_url: str
    source_locator: str
    parser_version: str
    extracted_at: str
    kam_items: list[KamItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    from_cache: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data.pop("from_cache", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KamResult":
        values = dict(data)
        values["status"] = ResultStatus(values["status"])
        values["kam_items"] = [KamItem(**item) for item in values.get("kam_items", [])]
        values.setdefault("warnings", [])
        values.setdefault("from_cache", False)
        return cls(**values)

    def to_rows(self) -> list[dict[str, Any]]:
        """KAM 하나를 한 행으로 하는 KAM_RESULT 형태로 펼친다."""
        common = {
            "corp_code": self.corp_code,
            "stock_code": self.stock_code,
            "corp_name": self.corp_name,
            "rcept_no": self.rcept_no,
            "report_period_end": self.report_period_end,
            "rcept_date": self.rcept_date,
            "is_amended": self.is_amended,
            "report_scope": self.report_scope,
            "auditor_name": self.auditor_name,
            "status": self.status.value,
            "confidence": self.confidence,
            "source_url": self.source_url,
            "parser_version": self.parser_version,
            "extracted_at": self.extracted_at,
        }
        if not self.kam_items:
            return [
                common
                | {
                    "id": f"{self.rcept_no}-status",
                    "kam_no": None,
                    "kam_title": None,
                    "why_kam": None,
                    "audit_response": None,
                    "raw_text": None,
                    "source_locator": self.source_locator,
                }
            ]
        return [
            common
            | {
                "id": f"{self.rcept_no}-{item.kam_no:02d}",
                "kam_no": item.kam_no,
                "kam_title": item.kam_title,
                "why_kam": item.why_kam,
                "audit_response": item.audit_response,
                "raw_text": item.raw_text,
                "source_locator": item.source_locator or self.source_locator,
            }
            for item in self.kam_items
        ]
